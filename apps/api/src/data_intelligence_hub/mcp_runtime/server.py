from __future__ import annotations

import uuid

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from data_intelligence_hub.mcp_runtime.collect_service import collect_capability
from data_intelligence_hub.mcp_runtime.run_service import (
    get_run_detail,
    list_run_records,
)
from data_intelligence_hub.mcp_runtime.runtime import governed_tool
from data_intelligence_hub.platform_packages.service import (
    CapabilityNotFoundError,
    PlatformPackageNotFoundError,
    get_capability,
    get_platform_package,
    get_platform_package_catalog,
    get_platform_playbook,
)
from data_intelligence_hub.services.tiktok_tools import run_tiktok_tool


def _parse_project_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("project_id_invalid") from exc


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
    async with governed_tool(context, "list_capabilities"):
        try:
            package = await get_platform_package(platform_id)
        except PlatformPackageNotFoundError as exc:
            raise ValueError("platform_package_not_found") from exc
        normalized = query.casefold().strip() if query else None
        capabilities = [
            endpoint
            for endpoint in package.endpoints
            if (status is None or endpoint.status == status)
            and (
                normalized is None
                or normalized
                in f"{endpoint.endpoint_type} {endpoint.label} {endpoint.description}".casefold()
            )
        ]
        catalog = await get_platform_package_catalog()
        return {
            "catalog_digest": catalog.catalog_digest,
            "platform_id": platform_id,
            "capabilities": [item.model_dump(mode="json") for item in capabilities],
        }


@mcp_server.tool(structured_output=True)
async def describe_capability(
    context: Context,
    endpoint_type: str,
) -> dict[str, object]:
    async with governed_tool(context, "describe_capability", endpoint_type=endpoint_type):
        try:
            endpoint = await get_capability(endpoint_type)
        except CapabilityNotFoundError as exc:
            raise ValueError("capability_not_found") from exc
        return endpoint.model_dump(mode="json")


@mcp_server.tool(structured_output=True)
async def get_playbook(context: Context, platform_id: str) -> dict[str, str]:
    async with governed_tool(context, "get_playbook"):
        try:
            markdown = await get_platform_playbook(platform_id)
        except PlatformPackageNotFoundError as exc:
            raise ValueError("platform_package_not_found") from exc
        return {"platform_id": platform_id, "markdown": markdown}


@mcp_server.tool(structured_output=True)
async def collect(
    context: Context,
    endpoint_type: str,
    project_id: str,
    params: dict[str, object],
) -> dict[str, object]:
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
        try:
            parsed_project_id = uuid.UUID(project_id)
        except ValueError as exc:
            raise ValueError("project_id_invalid") from exc
        result = await collect_capability(endpoint_type, parsed_project_id, params)
        return result.model_dump(mode="json")


@mcp_server.tool(structured_output=True)
async def get_run(context: Context, run_id: str) -> dict[str, object]:
    """Return one run with its status, outcome, cost and steps."""
    async with governed_tool(context, "get_run"):
        try:
            parsed = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        return await get_run_detail(parsed)


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
        return await list_run_records(parsed, limit=limit, cursor=cursor)


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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
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
            _parse_project_id(project_id),
            {"ad_id": ad_id},
        )
        return result.as_dict()


mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    transport_security=MCP_TRANSPORT_SECURITY,
)
