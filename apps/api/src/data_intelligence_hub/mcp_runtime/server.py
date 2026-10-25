from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations

from data_intelligence_hub.core.database import async_session_factory
from data_intelligence_hub.mcp_runtime.access_control import (
    AccessDecision,
    governed_mcp_tool,
    resolve_bound_project,
)
from data_intelligence_hub.mcp_runtime.auth import (
    ProjectApiKeyContext,
    project_api_key_context,
)
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
from data_intelligence_hub.mcp_runtime.tool_registry import TIKTOK_EXECUTE_TOOLS
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


def _assert_bound_project(
    identity: ProjectApiKeyContext | None,
    project_id: uuid.UUID,
) -> uuid.UUID:
    if identity is not None and project_id != identity.project_id:
        raise ValueError("project_not_found")
    return project_id


# 供测试与密钥页枚举执行类 TikTok 工具；事实源是 tool_registry。
_TIKTOK_TOOL_NAMES: tuple[str, ...] = TIKTOK_EXECUTE_TOOLS


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
        "scrapy.lute-tlz-dddd.top",
        "scrapy.lute-tlz-dddd.top:*",
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
        "test",
        "test:*",
    ],
    allowed_origins=[
        "https://scrapy.luteos.com",
        "https://scrapy.lute-tlz-dddd.top",
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
    async with governed_mcp_tool(context, "list_platforms"):
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
    async with governed_mcp_tool(context, "list_capabilities"):
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
            "capabilities": [_public_endpoint_payload(item) for item in capabilities],
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
    async with governed_mcp_tool(context, "describe_capability"):
        return await describe_capability_public(endpoint_type)


@_tool(
    description="Return the platform playbook in Markdown.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
async def get_playbook(context: Context, platform_id: str) -> dict[str, str]:
    async with governed_mcp_tool(context, "get_playbook"):
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
    async with governed_mcp_tool(
        context,
        "collect",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        try:
            endpoint = await get_capability(endpoint_type)
        except CapabilityNotFoundError as exc:
            raise ValueError("capability_not_found") from exc
        if endpoint.status == "disabled":
            raise ValueError("capability_disabled")
        bound_pid = resolve_bound_project(decision.identity, _parse_project_id(project_id))
        result = await collect_capability(
            endpoint_type,
            bound_pid,
            params,
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
        )
        return result.model_dump(mode="json")


# ── Exa MCP Pack ──────────────────────────────────────────────────────────
# 通用命名的搜索/抓取/问答/研究工具。默认路由 Exa；web_fetch 支持 jina。
# 项目密钥调用按 tool_allowlist 判定，见 mcp_runtime/access_control.py。

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


async def _run_tool(
    decision: AccessDecision,
    tool_name: str,
    endpoint_type: str,
    project_id: str,
    params: dict[str, object],
) -> dict[str, object]:
    identity = decision.identity
    result = await collect_capability(
        endpoint_type,
        resolve_bound_project(identity, _parse_project_id(project_id)),
        params,
        workspace_id=(identity.workspace_id if identity is not None else None),
        tool_call=_tool_call_metadata(identity, tool_name),
    )
    return result.model_dump(mode="json")


def _tool_call_metadata(identity: ProjectApiKeyContext | None, tool_name: str) -> dict[str, object]:
    """运行配置里的调用来源。项目密钥记 key_id，便于按密钥审计与对账。"""
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
    async with governed_mcp_tool(
        context, "web_search", project_id=project_id, is_collect=True
    ) as decision:
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
        return await _run_tool(decision, "web_search", endpoint_type, project_id, params)


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
    async with governed_mcp_tool(
        context, "web_fetch", project_id=project_id, is_collect=True
    ) as decision:
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
        return await _run_tool(decision, "web_fetch", endpoint_type, project_id, params)


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
    async with governed_mcp_tool(
        context, "answer", project_id=project_id, is_collect=True
    ) as decision:
        params: dict[str, object] = {"query": query}
        if output_schema is not None:
            params["output_schema"] = output_schema
        if text:
            params["text"] = True
        return await _run_tool(decision, "answer", "exa_answer", project_id, params)


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
    async with governed_mcp_tool(
        context, "deep_research", project_id=project_id, is_collect=True
    ) as decision:
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
        return await _run_tool(decision, "deep_research", "exa_deep_research", project_id, params)


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
    async with governed_mcp_tool(
        context, "create_monitor", project_id=project_id, is_collect=True
    ) as decision:
        workspace = await _monitor_workspace(context)
        bound_pid = resolve_bound_project(decision.identity, _parse_project_id(project_id))
        async with async_session_factory() as session:
            project = await get_project(session, workspace.id, bound_pid)
            if project is None:
                raise ValueError("project_not_found")
            monitor = await monitor_service.create_monitor(
                session,
                workspace=workspace,
                project_id=bound_pid,
                name=name,
                endpoint_type=endpoint_type,
                params=params or {},
                interval_hours=interval_hours,
                # 密钥身份记进监控归属；调度器按它扣日额度。全局 token 为 None。
                project_key_id=(
                    decision.identity.key_id if decision.identity else None
                ),
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
    async with governed_mcp_tool(
        context,
        "list_monitors",
        project_id=project_id,
    ) as decision:
        workspace = await _monitor_workspace(context)
        parsed = (
            resolve_bound_project(decision.identity, _parse_project_id(project_id))
            if project_id
            else None
        )
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
) -> dict[str, object]:
    """Answer strictly from workspace records. Use answer for external web evidence."""
    async with governed_mcp_tool(context, "workspace_answer"):
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
    async with governed_mcp_tool(
        context, "deep_research_start", project_id=project_id, is_collect=True
    ) as decision:
        workspace = await _monitor_workspace(context)
        bound_pid = resolve_bound_project(decision.identity, _parse_project_id(project_id))
        async with async_session_factory() as session:
            project = await get_project(session, workspace.id, bound_pid)
            if project is None:
                raise ValueError("project_not_found")
            run_id = await start_research(
                session,
                workspace=workspace,
                project_id=bound_pid,
                query=query,
                effort=effort,
                output_schema=output_schema,
                max_cost_dollars=max_cost_dollars,
                timeout_seconds=timeout_seconds,
                trigger="mcp",
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
    async with governed_mcp_tool(context, "deep_research_check"):
        parsed = uuid.UUID(run_id)
        identity = project_api_key_context(context)
        workspace_id = identity.workspace_id if identity is not None else None
        detail = await get_run_detail(parsed, workspace_id=workspace_id)
        records = await list_run_records(
            parsed,
            limit=20,
            workspace_id=workspace_id,
        )
        for item in records.get("items", []):
            if isinstance(item, dict) and item.get("id"):
                item["record_url"] = f"/api/raw-records/{item['id']}"
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
    async with governed_mcp_tool(
        context, "enrich_list", project_id=project_id, is_collect=True
    ) as decision:
        workspace = await _monitor_workspace(context)
        bound_pid = resolve_bound_project(decision.identity, _parse_project_id(project_id))
        async with async_session_factory() as session:
            project = await get_project(session, workspace.id, bound_pid)
            if project is None:
                raise ValueError("project_not_found")
            identity = project_api_key_context(context)
            job = await enrichment_service.start_enrichment(
                session,
                workspace=workspace,
                project_id=bound_pid,
                name=name,
                query_template=query_template,
                items=items,
                output_schema=output_schema,
                project_key_id=(identity.key_id if identity is not None else None),
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
    async with governed_mcp_tool(context, "enrichment_check"):
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
    async with governed_mcp_tool(context, "get_run"):
        try:
            parsed = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        identity = project_api_key_context(context)
        workspace_id = identity.workspace_id if identity is not None else None
        return await get_run_detail(parsed, workspace_id=workspace_id)


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
    async with governed_mcp_tool(context, "list_records"):
        try:
            parsed = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        identity = project_api_key_context(context)
        workspace_id = identity.workspace_id if identity is not None else None
        return await list_run_records(
            parsed,
            limit=limit,
            cursor=cursor,
            workspace_id=workspace_id,
        )


@_tool(
    description="Cancel a queued or running run.",
    read_only=False,
    open_world=False,
    destructive=True,
    idempotent=False,
)
async def stop(context: Context, run_id: str) -> dict[str, object]:
    """Cancel a queued or running run."""
    async with governed_mcp_tool(context, "stop"):
        try:
            parsed = uuid.UUID(run_id)
        except ValueError as exc:
            raise ValueError("run_id_invalid") from exc
        identity = project_api_key_context(context)
        workspace_id = identity.workspace_id if identity is not None else None
        return await stop_run(parsed, workspace_id=workspace_id)


@_tool(
    description="Report project spend and remaining authorized budget.",
    read_only=True,
    open_world=False,
    destructive=False,
    idempotent=False,
)
async def balance(context: Context, project_id: str) -> dict[str, object]:
    """Report project spend and remaining authorized budget."""
    async with governed_mcp_tool(context, "balance", project_id=project_id) as decision:
        bound_pid = resolve_bound_project(decision.identity, _parse_project_id(project_id))
        return await get_project_balance(bound_pid)


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
    async with governed_mcp_tool(
        context, "tiktok_trend_rank", project_id=project_id, is_collect=True
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_trend_rank",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"country_code": country_code, "period": period, "limit": limit},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_hashtag_videos",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_hashtag_videos",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {
                "hashtag": hashtag,
                "ch_id": ch_id,
                "challenge_id": challenge_id,
                "limit": limit,
            },
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_video_search",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_video_search",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"query": query, "limit": limit},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_video_detail",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_video_detail",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"video_id": video_id, "video_url": video_url},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_video_comments",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_video_comments",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {
                "video_id": video_id,
                "video_url": video_url,
                "limit": limit,
                "include_replies": include_replies,
            },
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_creator_profile",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_creator_profile",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {
                "handle": handle,
                "sec_uid": sec_uid,
                "include_videos": include_videos,
                "video_limit": video_limit,
                "include_fans": include_fans,
            },
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_creator_search",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_creator_search",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"query": query, "limit": limit},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_transcript",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_transcript",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"video_urls": video_urls, "limit": limit},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_product_search",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_product_search",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"query": query, "region": region, "limit": limit},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_product_detail",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_product_detail",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {
                "product_id": product_id,
                "product_url": product_url,
                "region": region,
            },
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_product_reviews",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_product_reviews",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"product_id": product_id, "region": region, "limit": limit},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_creator_commerce",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_creator_commerce",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"handle": handle, "region": region},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_video_products",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_video_products",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"video_id": video_id},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_creator_showcase",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_creator_showcase",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"offset": offset, "limit": limit},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_ads_top",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_ads_top",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"query": query, "period": period, "limit": limit},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
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
    async with governed_mcp_tool(
        context,
        "tiktok_ads_detail",
        project_id=project_id,
        is_collect=True,
    ) as decision:
        result = await run_tiktok_tool(
            "tiktok_ads_detail",
            resolve_bound_project(decision.identity, _parse_project_id(project_id)),
            {"ad_id": ad_id},
            workspace_id=(decision.identity.workspace_id if decision.identity else None),
        )
        return result.as_dict()


mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    transport_security=MCP_TRANSPORT_SECURITY,
)
