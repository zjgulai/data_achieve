from __future__ import annotations

import uuid

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from data_intelligence_hub.mcp_runtime.collect_service import collect_capability
from data_intelligence_hub.mcp_runtime.run_service import (
    get_run_detail,
    list_run_records,
)
from data_intelligence_hub.mcp_runtime.runtime import (
    governed_tool,
    project_filter,
    project_identity,
    project_workspace_id,
    require_project_access,
)
from data_intelligence_hub.mcp_runtime.tools.discovery import (
    discover as discover_tools,
)
from data_intelligence_hub.mcp_runtime.tools.discovery import (
    inspect_tool,
    load_catalog,
    structured_playbook,
)
from data_intelligence_hub.mcp_runtime.tools.reports import (
    create_report as create_report_artifact,
)
from data_intelligence_hub.platform_packages.service import (
    CapabilityNotFoundError,
    PlatformPackageNotFoundError,
    get_capability,
    get_platform_package,
    get_platform_package_catalog,
)
from data_intelligence_hub.services.tiktok_tools import run_tiktok_tool


def _parse_project_id(value: str, context: Context) -> uuid.UUID:
    """解析项目标识，并校验项目密钥的访问范围。"""
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("project_id_invalid") from exc
    return require_project_access(context, parsed)


mcp_server = MCPServer(
    "Data Intelligence Hub",
    instructions=(
        "Discover capabilities before collecting. Never request provider secrets. "
        "Collect only non-disabled endpoints with an explicit project_id."
    ),
)

MCP_TRANSPORT_SECURITY = TransportSecuritySettings(
    allowed_hosts=[
        "scrapy.luteos.com",
        "scrapy.luteos.com:*",
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
        "test",
        "test:*",
    ],
    allowed_origins=[
        "https://scrapy.luteos.com",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://test",
    ],
)


@mcp_server.tool(structured_output=True)
async def list_platforms(context: Context, query: str | None = None) -> dict[str, object]:
    async with governed_tool(context, "list_platforms"):
        catalog = await get_platform_package_catalog()
        normalized = query.casefold().strip() if query else None
        packages = [
            package
            for package in catalog.packages
            if normalized is None
            or normalized in f"{package.platform_id} {package.display_name}".casefold()
        ]
        return {
            "catalog_digest": catalog.catalog_digest,
            "platforms": [
                {
                    "platform_id": package.platform_id,
                    "display_name": package.display_name,
                    "endpoint_count": package.endpoint_count,
                    "verified_count": package.verified_count,
                    "methods": list(package.methods),
                }
                for package in packages
            ],
        }


@mcp_server.tool(structured_output=True)
async def list_capabilities(
    context: Context,
    platform_id: str,
    query: str | None = None,
    status: str | None = None,
) -> dict[str, object]:
    """列出某个平台的工具目录投影。"""
    async with governed_tool(context, "list_capabilities"):
        try:
            await get_platform_package(platform_id)
        except PlatformPackageNotFoundError as exc:
            raise ValueError("platform_package_not_found") from exc
        catalog = await load_catalog()
        normalized = query.casefold().strip() if query else None
        capabilities: list[dict[str, object]] = []
        for tool in catalog.tools:
            if tool.platform != platform_id:
                continue
            if status is not None and tool.availability_view.catalog_status != status:
                continue
            if normalized is not None and normalized not in (
                f"{tool.tool_id} {tool.label} {tool.description}".casefold()
            ):
                continue
            item = tool.model_dump(mode="json")
            # 旧调用方读 ``endpoint_type``。保留同值别名。
            item["endpoint_type"] = tool.tool_id
            capabilities.append(item)
        return {
            "catalog_digest": catalog.catalog_digest,
            "contract_version": catalog.contract_version,
            "platform_id": platform_id,
            "capabilities": capabilities,
        }


@mcp_server.tool(structured_output=True)
async def describe_capability(
    context: Context,
    endpoint_type: str,
) -> dict[str, object]:
    """返回一个能力的完整工具契约。

    ``endpoint_type`` 与目录的 ``tool_id`` 同值。
    """
    async with governed_tool(context, "describe_capability", endpoint_type=endpoint_type):
        payload = await inspect_tool(endpoint_type)
        # 旧调用方读 ``endpoint_type``。保留同值别名，不改变契约本身。
        payload["endpoint_type"] = payload["tool_id"]
        return payload


@mcp_server.tool(structured_output=True)
async def get_playbook(context: Context, platform_id: str) -> dict[str, object]:
    """返回结构化 playbook，含能力、坑点、步骤、验收与风险边界。"""
    async with governed_tool(context, "get_playbook"):
        try:
            return await structured_playbook(platform_id)
        except PlatformPackageNotFoundError as exc:
            raise ValueError("platform_package_not_found") from exc


@mcp_server.tool(structured_output=True)
async def discover(
    context: Context,
    query: str,
    limit: int = 10,
) -> dict[str, object]:
    """按自然语言检索工具，返回带命中理由的候选。"""
    async with governed_tool(context, "discover"):
        return await discover_tools(query, limit)


@mcp_server.tool(structured_output=True)
async def inspect(context: Context, tool_id: str) -> dict[str, object]:
    """返回完整工具契约，含输入 schema、输出字段、成本与风险。"""
    async with governed_tool(context, "inspect"):
        return await inspect_tool(tool_id)


@mcp_server.tool(structured_output=True)
async def collect(
    context: Context,
    endpoint_type: str,
    project_id: str,
    params: dict[str, object],
) -> dict[str, object]:
    """执行一次采集。项目密钥只能采集自己的项目。"""
    async with governed_tool(
        context,
        "collect",
        endpoint_type=endpoint_type,
        is_collect=True,
    ):
        try:
            endpoint = await get_capability(endpoint_type)
        except CapabilityNotFoundError as exc:
            raise ValueError("capability_not_found") from exc
        if endpoint.status == "disabled":
            raise ValueError("capability_disabled")
        parsed_project_id = _parse_project_id(project_id, context)
        result = await collect_capability(
            endpoint_type,
            parsed_project_id,
            params,
            workspace_id=project_workspace_id(context),
        )
        return result.model_dump(mode="json")


@mcp_server.tool(structured_output=True)
async def get_run(context: Context, run_id: str) -> dict[str, object]:
    """Return one run with its status, outcome, cost and steps."""
    async with governed_tool(context, "get_run"):
        try:
            parsed = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        return await get_run_detail(parsed, project_id=project_filter(context))


@mcp_server.tool(structured_output=True)
async def list_records(
    context: Context,
    run_id: str,
    limit: int = 20,
    cursor: str | None = None,
) -> dict[str, object]:
    """List raw records for one run. Page with limit and cursor."""
    async with governed_tool(context, "list_records"):
        try:
            parsed = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        return await list_run_records(
            parsed,
            limit=limit,
            cursor=cursor,
            project_id=project_filter(context),
        )


@mcp_server.tool(structured_output=True)
async def create_report(
    context: Context,
    run_id: str,
    template_id: str,
    contract: dict[str, object] | None = None,
) -> dict[str, object]:
    """用完整合同生成报告与 SOP 产物。

    运行数据不能填满合同。缺少合同组时返回明确错误。
    """
    async with governed_tool(context, "create_report"):
        try:
            parsed_run_id = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        identity = project_identity(context)
        return await create_report_artifact(
            parsed_run_id,
            template_id,
            contract,
            project_id=identity.project_id if identity is not None else None,
            workspace_id=identity.workspace_id if identity is not None else None,
        )


@mcp_server.tool(structured_output=True)
async def tiktok_trend_rank(
    context: Context,
    project_id: str,
    country_code: str = "US",
    period: int = 7,
    limit: int = 50,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_trend_rank", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_trend_rank",
            _parse_project_id(project_id, context),
            {"country_code": country_code, "period": period, "limit": limit},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_hashtag_videos(
    context: Context,
    project_id: str,
    hashtag: str | None = None,
    ch_id: str | None = None,
    challenge_id: str | None = None,
    limit: int = 50,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_hashtag_videos", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_hashtag_videos",
            _parse_project_id(project_id, context),
            {
                "hashtag": hashtag,
                "ch_id": ch_id,
                "challenge_id": challenge_id,
                "limit": limit,
            },
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_video_search(
    context: Context,
    project_id: str,
    query: str,
    limit: int = 50,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_video_search", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_video_search",
            _parse_project_id(project_id, context),
            {"query": query, "limit": limit},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_video_detail(
    context: Context,
    project_id: str,
    video_id: str | None = None,
    video_url: str | None = None,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_video_detail", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_video_detail",
            _parse_project_id(project_id, context),
            {"video_id": video_id, "video_url": video_url},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_video_comments(
    context: Context,
    project_id: str,
    video_id: str,
    video_url: str | None = None,
    limit: int = 100,
    include_replies: bool = True,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_video_comments", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_video_comments",
            _parse_project_id(project_id, context),
            {
                "video_id": video_id,
                "video_url": video_url,
                "limit": limit,
                "include_replies": include_replies,
            },
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_creator_profile(
    context: Context,
    project_id: str,
    handle: str | None = None,
    sec_uid: str | None = None,
    include_videos: bool = True,
    video_limit: int = 20,
    include_fans: bool = False,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_creator_profile", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_creator_profile",
            _parse_project_id(project_id, context),
            {
                "handle": handle,
                "sec_uid": sec_uid,
                "include_videos": include_videos,
                "video_limit": video_limit,
                "include_fans": include_fans,
            },
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_creator_search(
    context: Context,
    project_id: str,
    query: str,
    limit: int = 50,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_creator_search", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_creator_search",
            _parse_project_id(project_id, context),
            {"query": query, "limit": limit},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_transcript(
    context: Context,
    project_id: str,
    video_urls: list[str],
    limit: int = 20,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_transcript", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_transcript",
            _parse_project_id(project_id, context),
            {"video_urls": video_urls, "limit": limit},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_product_search(
    context: Context,
    project_id: str,
    query: str,
    region: str = "US",
    limit: int = 20,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_product_search", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_product_search",
            _parse_project_id(project_id, context),
            {"query": query, "region": region, "limit": limit},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_product_detail(
    context: Context,
    project_id: str,
    product_id: str | None = None,
    product_url: str | None = None,
    region: str = "US",
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_product_detail", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_product_detail",
            _parse_project_id(project_id, context),
            {
                "product_id": product_id,
                "product_url": product_url,
                "region": region,
            },
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_product_reviews(
    context: Context,
    project_id: str,
    product_id: str,
    region: str = "US",
    limit: int = 20,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_product_reviews", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_product_reviews",
            _parse_project_id(project_id, context),
            {"product_id": product_id, "region": region, "limit": limit},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_creator_commerce(
    context: Context,
    project_id: str,
    handle: str,
    region: str = "US",
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_creator_commerce", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_creator_commerce",
            _parse_project_id(project_id, context),
            {"handle": handle, "region": region},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_video_products(
    context: Context,
    project_id: str,
    video_id: str,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_video_products", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_video_products",
            _parse_project_id(project_id, context),
            {"video_id": video_id},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_creator_showcase(
    context: Context,
    project_id: str,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_creator_showcase", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_creator_showcase",
            _parse_project_id(project_id, context),
            {"offset": offset, "limit": limit},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_ads_top(
    context: Context,
    project_id: str,
    query: str = "",
    period: int = 7,
    limit: int = 20,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_ads_top", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_ads_top",
            _parse_project_id(project_id, context),
            {"query": query, "period": period, "limit": limit},
        )
        return result.as_dict()


@mcp_server.tool(structured_output=True)
async def tiktok_ads_detail(
    context: Context,
    project_id: str,
    ad_id: str,
) -> dict[str, object]:
    async with governed_tool(context, "tiktok_ads_detail", is_collect=True):
        result = await run_tiktok_tool(
            "tiktok_ads_detail",
            _parse_project_id(project_id, context),
            {"ad_id": ad_id},
        )
        return result.as_dict()


mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    transport_security=MCP_TRANSPORT_SECURITY,
)
