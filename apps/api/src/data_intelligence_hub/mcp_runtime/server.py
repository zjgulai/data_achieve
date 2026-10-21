from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.mcp_runtime.auth import project_api_key_context
from data_intelligence_hub.mcp_runtime.capability_service import (
    describe_capability_public,
)
from data_intelligence_hub.mcp_runtime.collect_service import collect_capability
from data_intelligence_hub.mcp_runtime.run_service import (
    get_project_balance,
    get_run_detail,
    list_run_records,
    stop_run,
)
from data_intelligence_hub.mcp_runtime.runtime import governed_tool
from data_intelligence_hub.mcp_runtime.tool_policy import (
    enforce_quota,
    enforce_tool_policy,
)
from data_intelligence_hub.models.run import Run
from data_intelligence_hub.platform_packages.service import (
    CapabilityNotFoundError,
    PlatformPackageNotFoundError,
    get_capability,
    get_platform_package,
    get_platform_package_catalog,
    get_platform_playbook,
)
from data_intelligence_hub.repositories.projects import get_project
from data_intelligence_hub.repositories.workspaces import (
    get_demo_workspace,
    get_workspace_by_id,
)
from data_intelligence_hub.services import enrichment_service, monitor_service
from data_intelligence_hub.services.answer_service import (
    workspace_answer as run_workspace_answer,
)
from data_intelligence_hub.services.research_service import start_research
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

def _public_endpoint_payload(endpoint: object) -> dict[str, object]:
    """去掉策略拒绝原文。它是内部治理信息。"""
    payload: dict[str, Any] = endpoint.model_dump(mode="json")  # type: ignore[attr-defined]
    payload.pop("policy_block_reason", None)
    return payload


def _tool(
    *,
    description: str,
    read_only: bool,
    open_world: bool,
    destructive: bool = False,
    idempotent: bool = False,
) -> Callable[[Any], Any]:
    """统一注册带描述与注解的工具。"""
    return mcp_server.tool(
        description=description,
        annotations=ToolAnnotations(
            readOnlyHint=read_only,
            destructiveHint=destructive,
            idempotentHint=idempotent,
            openWorldHint=open_world,
        ),
        structured_output=True,
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


@_tool(
    description="List available data platforms and their endpoint counts.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="List capabilities for one platform, with optional text and status filters.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
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
            "capabilities": [
                _public_endpoint_payload(item) for item in capabilities
            ],
        }


@_tool(
    description="Describe one capability with typed input and output JSON schemas.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
async def describe_capability(
    context: Context,
    endpoint_type: str,
) -> dict[str, object]:
    async with governed_tool(context, "describe_capability", endpoint_type=endpoint_type):
        return await describe_capability_public(endpoint_type)


@_tool(
    description="Return the platform playbook in Markdown.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
async def get_playbook(context: Context, platform_id: str) -> dict[str, str]:
    async with governed_tool(context, "get_playbook"):
        try:
            markdown = await get_platform_playbook(platform_id)
        except PlatformPackageNotFoundError as exc:
            raise ValueError("platform_package_not_found") from exc
        return {"platform_id": platform_id, "markdown": markdown}


@_tool(
    description="Run one collection and return records, output, usage and timing.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


# ── Exa MCP Pack ──────────────────────────────────────────────────────────
# 通用命名的搜索/抓取/问答/研究工具。默认路由 Exa；web_fetch 支持 jina。
# 项目密钥调用按 tool_allowlist 判定，见 mcp_runtime/tool_policy.py。

_SEARCH_ENDPOINTS = {
    "lite": "exa_search_lite",
    "instant": "exa_search_instant",
    "fast": "exa_search_fast",
    "auto": "exa_search_auto",
    "deep-lite": "exa_deep_lite",
    "deep": "exa_deep_research",
    "deep-reasoning": "exa_deep_reasoning",
}

_FETCH_ENDPOINTS = {"exa": "exa_contents", "jina": "jina_page_content"}


def _workspace_binding(context: Context) -> uuid.UUID | None:
    identity = project_api_key_context(context)
    return identity.workspace_id if identity is not None else None


async def _run_tool(
    context: Context,
    tool_name: str,
    endpoint_type: str,
    project_id: str,
    params: dict[str, object],
) -> dict[str, object]:
    await enforce_tool_policy(context, tool_name)
    await enforce_quota(context)
    result = await collect_capability(
        endpoint_type,
        _parse_project_id(project_id),
        params,
        workspace_id=_workspace_binding(context),
        tool_call=_tool_call_metadata(context, tool_name),
    )
    return result.model_dump(mode="json")


def _tool_call_metadata(context: Context, tool_name: str) -> dict[str, object]:
    """运行配置里的调用来源。项目密钥记 key_id，便于按密钥审计与对账。"""
    identity = project_api_key_context(context)
    metadata: dict[str, object] = {"origin": "mcp", "tool": tool_name}
    if identity is not None:
        metadata["key_id"] = str(identity.key_id)
        metadata["project_id"] = str(identity.project_id)
    return metadata


@_tool(
    description="Search the web and persist results. Default provider: exa.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
async def web_search(
    context: Context,
    project_id: str,
    query: str,
    search_type: str = "auto",
    num_results: int = 10,
    category: str | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    contents_mode: str = "highlights",
    start_published_date: str | None = None,
    end_published_date: str | None = None,
    objective: str | None = None,
    provider: str = "exa",
) -> dict[str, object]:
    """Search the web and persist results. Default provider: exa."""
    async with governed_tool(context, "web_search", is_collect=True):
        if provider != "exa":
            raise ValueError("provider_not_supported")
        endpoint_type = _SEARCH_ENDPOINTS.get(search_type)
        if endpoint_type is None:
            raise ValueError("search_type_invalid")
        params: dict[str, object] = {
            "query": query,
            "num_results": num_results,
            "contents_mode": contents_mode,
        }
        if category is not None:
            params["category"] = category
        if include_domains:
            params["include_domains"] = include_domains
        if exclude_domains:
            params["exclude_domains"] = exclude_domains
        if start_published_date is not None:
            params["start_published_date"] = start_published_date
        if end_published_date is not None:
            params["end_published_date"] = end_published_date
        if objective is not None:
            params["objective"] = objective
        return await _run_tool(context, "web_search", endpoint_type, project_id, params)


@_tool(
    description="Fetch page content for up to 100 URLs. Default provider: exa; jina takes one URL.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
async def web_fetch(
    context: Context,
    project_id: str,
    urls: list[str],
    contents_mode: str = "text",
    max_age_hours: int | None = None,
    summary_query: str | None = None,
    provider: str = "exa",
) -> dict[str, object]:
    """Fetch page content for up to 100 URLs. Default provider: exa; jina takes one URL."""
    async with governed_tool(context, "web_fetch", is_collect=True):
        endpoint_type = _FETCH_ENDPOINTS.get(provider)
        if endpoint_type is None:
            raise ValueError("provider_not_supported")
        if not urls:
            raise ValueError("urls_required")
        if provider == "jina":
            if len(urls) != 1:
                raise ValueError("provider_urls_limit")
            params: dict[str, object] = {"url": urls[0], "return_format": "markdown"}
        else:
            params = {"urls": urls, "contents_mode": contents_mode}
            if max_age_hours is not None:
                params["max_age_hours"] = max_age_hours
            if summary_query is not None:
                params["summary_query"] = summary_query
        return await _run_tool(context, "web_fetch", endpoint_type, project_id, params)


@_tool(
    description="Answer a question with citations from the public web.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
async def answer(
    context: Context,
    project_id: str,
    query: str,
    output_schema: dict[str, object] | None = None,
    text: bool = False,
) -> dict[str, object]:
    """Answer a question with citations from the public web."""
    async with governed_tool(context, "answer", is_collect=True):
        params: dict[str, object] = {"query": query}
        if output_schema is not None:
            params["output_schema"] = output_schema
        if text:
            params["text"] = True
        return await _run_tool(context, "answer", "exa_answer", project_id, params)


@_tool(
    description="Multi-step deep research. Expensive; needs allowlist entry for keys.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
async def deep_research(
    context: Context,
    project_id: str,
    query: str,
    num_results: int = 10,
    output_schema: dict[str, object] | None = None,
    system_prompt: str | None = None,
    include_domains: list[str] | None = None,
    contents_mode: str = "highlights",
) -> dict[str, object]:
    """Multi-step deep research. Expensive tool; project keys need it in their allowlist."""
    async with governed_tool(context, "deep_research", is_collect=True):
        params: dict[str, object] = {
            "query": query,
            "num_results": num_results,
            "contents_mode": contents_mode,
        }
        if output_schema is not None:
            params["output_schema"] = output_schema
        if system_prompt is not None:
            params["system_prompt"] = system_prompt
        if include_domains:
            params["include_domains"] = include_domains
        return await _run_tool(
            context, "deep_research", "exa_deep_research", project_id, params
        )


# ── Monitors ──────────────────────────────────────────────────────────────


async def _monitor_workspace(context: Context):
    identity = project_api_key_context(context)
    async with async_session_factory() as session:
        if identity is not None:
            workspace = await get_workspace_by_id(session, identity.workspace_id)
        else:
            workspace = await get_demo_workspace(session)
    if workspace is None:
        raise ValueError("workspace_unavailable")
    return workspace


@_tool(
    description="Create a search monitor on one endpoint; it reruns on a fixed interval.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
async def create_monitor(
    context: Context,
    project_id: str,
    name: str,
    endpoint_type: str,
    params: dict[str, object] | None = None,
    interval_hours: int = 24,
) -> dict[str, object]:
    """Create a search monitor. New results become signals and notifications."""
    async with governed_tool(context, "create_monitor", is_collect=True):
        await enforce_tool_policy(context, "create_monitor")
        workspace = await _monitor_workspace(context)
        parsed_project_id = _parse_project_id(project_id)
        async with async_session_factory() as session:
            project = await get_project(session, workspace.id, parsed_project_id)
            if project is None:
                raise ValueError("project_not_found")
            monitor = await monitor_service.create_monitor(
                session,
                workspace=workspace,
                project_id=parsed_project_id,
                name=name,
                endpoint_type=endpoint_type,
                params=params or {},
                interval_hours=interval_hours,
            )
        return _monitor_payload(monitor)


@_tool(
    description="List search monitors in the current workspace.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=True,
)
async def list_monitors(
    context: Context,
    project_id: str | None = None,
) -> dict[str, object]:
    """List monitors. Optionally filter by project."""
    async with governed_tool(context, "list_monitors"):
        workspace = await _monitor_workspace(context)
        parsed = _parse_project_id(project_id) if project_id else None
        async with async_session_factory() as session:
            monitors = await monitor_service.list_monitors(
                session, workspace_id=workspace.id, project_id=parsed
            )
        return {"monitors": [_monitor_payload(item) for item in monitors]}


def _monitor_payload(monitor) -> dict[str, object]:
    return {
        "id": str(monitor.id),
        "project_id": str(monitor.project_id),
        "name": monitor.name,
        "endpoint_type": monitor.endpoint_type,
        "interval_hours": monitor.interval_hours,
        "status": monitor.status,
        "task_id": str(monitor.task_id) if monitor.task_id else None,
        "last_checked_at": (
            monitor.last_checked_at.isoformat() if monitor.last_checked_at else None
        ),
        "last_new_count": monitor.last_new_count,
    }


@_tool(
    description="Answer a question from this workspace's records, with citations.",
    read_only=True,
    open_world=True,
    destructive=False,
    idempotent=True,
)
async def workspace_answer(
    context: Context,
    query: str,
    project_id: str | None = None,
    limit: int = 5,
    allow_external: bool = True,
) -> dict[str, object]:
    """Answer from workspace records first; optionally supplement with Exa."""
    async with governed_tool(context, "workspace_answer"):
        workspace = await _monitor_workspace(context)
        parsed = _parse_project_id(project_id) if project_id else None
        async with async_session_factory() as session:
            if parsed is not None:
                project = await get_project(session, workspace.id, parsed)
                if project is None:
                    raise ValueError("project_not_found")
            return await run_workspace_answer(
                session,
                workspace_id=workspace.id,
                project_id=parsed,
                query=query,
                limit=limit,
                allow_external=allow_external,
            )


@_tool(
    description="Start an async deep research run; poll deep_research_check with the run_id.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
async def deep_research_start(
    context: Context,
    project_id: str,
    query: str,
    effort: str = "medium",
    output_schema: dict[str, object] | None = None,
    max_cost_dollars: float = 5.0,
    timeout_seconds: int = 600,
) -> dict[str, object]:
    """Queue an Exa Agent research run. Expensive; keys need it in their allowlist."""
    async with governed_tool(context, "deep_research_start", is_collect=True):
        await enforce_tool_policy(context, "deep_research_start")
        await enforce_quota(context)
        workspace = await _monitor_workspace(context)
        parsed_project_id = _parse_project_id(project_id)
        async with async_session_factory() as session:
            project = await get_project(session, workspace.id, parsed_project_id)
            if project is None:
                raise ValueError("project_not_found")
            run_id = await start_research(
                session,
                workspace=workspace,
                project_id=parsed_project_id,
                query=query,
                effort=effort,
                output_schema=output_schema,
                max_cost_dollars=max_cost_dollars,
                timeout_seconds=timeout_seconds,
            )
        return {"run_id": str(run_id), "status": "queued"}


@_tool(
    description="Check an async research run: status, steps and records.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=True,
)
async def deep_research_check(
    context: Context,
    run_id: str,
) -> dict[str, object]:
    """Return one research run's status, steps and records."""
    async with governed_tool(context, "deep_research_check"):
        parsed = uuid.UUID(run_id)
        identity = project_api_key_context(context)
        if identity is not None:
            async with async_session_factory() as session:
                run = await session.get(Run, parsed)
            if run is None or run.workspace_id != identity.workspace_id:
                raise ValueError("run_not_found")
        detail = await get_run_detail(parsed)
        records = await list_run_records(parsed, limit=20)
        return {"run": detail, "records": records}


@_tool(
    description="Start an enrichment job over a list of rows with an output schema.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
async def enrich_list(
    context: Context,
    project_id: str,
    name: str,
    query_template: str,
    items: list[dict[str, object]],
    output_schema: dict[str, object],
) -> dict[str, object]:
    """Enrich rows one by one. Non-PII fields only; up to 100 rows."""
    async with governed_tool(context, "enrich_list", is_collect=True):
        await enforce_tool_policy(context, "enrich_list")
        workspace = await _monitor_workspace(context)
        parsed_project_id = _parse_project_id(project_id)
        async with async_session_factory() as session:
            project = await get_project(session, workspace.id, parsed_project_id)
            if project is None:
                raise ValueError("project_not_found")
            job = await enrichment_service.start_enrichment(
                session,
                workspace=workspace,
                project_id=parsed_project_id,
                name=name,
                query_template=query_template,
                items=items,
                output_schema=output_schema,
            )
        return {
            "job_id": str(job.id),
            "status": job.status,
            "total": job.total,
        }


@_tool(
    description="Check an enrichment job: status plus per-row output.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=True,
)
async def enrichment_check(
    context: Context,
    job_id: str,
) -> dict[str, object]:
    """Return one enrichment job with its rows."""
    async with governed_tool(context, "enrichment_check"):
        workspace = await _monitor_workspace(context)
        parsed = uuid.UUID(job_id)
        async with async_session_factory() as session:
            job = await enrichment_service.get_job(session, workspace.id, parsed)
            if job is None:
                raise ValueError("enrichment_job_not_found")
            rows = await enrichment_service.get_rows(session, job.id)
            return {
                "job_id": str(job.id),
                "status": job.status,
                "total": job.total,
                "processed": job.processed,
                "failed": job.failed,
                "rows": [
                    {
                        "row_index": row.row_index,
                        "status": row.status,
                        "output": row.output,
                        "error": row.error,
                    }
                    for row in rows
                ],
            }


@_tool(
    description="Return one run with status, outcome, cost and steps.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
async def get_run(context: Context, run_id: str) -> dict[str, object]:
    """Return one run with its status, outcome, cost and steps."""
    async with governed_tool(context, "get_run"):
        try:
            parsed = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        return await get_run_detail(parsed)


@_tool(
    description="List raw records for one run with cursor pagination.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Cancel a queued or running run.",
    read_only=False,
    open_world=False,
    destructive=True,
    idempotent=False,
)
async def stop(context: Context, run_id: str) -> dict[str, object]:
    """Cancel a queued or running run."""
    async with governed_tool(context, "stop"):
        try:
            parsed = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        return await stop_run(parsed)


@_tool(
    description="Report project spend and remaining authorized budget.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
async def balance(context: Context, project_id: str) -> dict[str, object]:
    """Report project spend and remaining authorized budget."""
    async with governed_tool(context, "balance"):
        try:
            parsed = uuid.UUID(project_id)
        except ValueError as exc:
            raise ValueError("project_id_invalid") from exc
        return await get_project_balance(parsed)


@_tool(
    description="TikTok trend ranking from Creative Center.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Videos for a TikTok hashtag.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Search public TikTok videos by keyword.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get one TikTok video by id or URL.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get comments for a TikTok video, optionally with replies.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get a TikTok creator profile, optionally with videos and fans.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Find TikTok creator candidates from keyword video results.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Extract a transcript or captions for TikTok videos.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Search TikTok Shop products by keyword.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get TikTok Shop product detail, GMV and SKUs.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get TikTok Shop product reviews and ratings.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get a TikTok creator commerce profile by handle.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get products linked to a TikTok video. Needs a creator cookie.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get a TikTok creator showcase product list. Needs a creator cookie.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get top TikTok ads with engagement metrics.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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


@_tool(
    description="Get TikTok ad detail, advertiser and landing page.",
    read_only=False,
    open_world=True,
    destructive=False,
    idempotent=False,
)
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
