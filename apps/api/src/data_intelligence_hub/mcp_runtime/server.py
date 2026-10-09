from __future__ import annotations

import uuid

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from data_intelligence_hub.mcp_runtime.collect_service import collect_capability
from data_intelligence_hub.mcp_runtime.runtime import governed_tool
from data_intelligence_hub.platform_packages.service import (
    CapabilityNotFoundError,
    PlatformPackageNotFoundError,
    get_capability,
    get_platform_package,
    get_platform_package_catalog,
    get_platform_playbook,
)

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
        return {
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


mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    transport_security=MCP_TRANSPORT_SECURITY,
)
