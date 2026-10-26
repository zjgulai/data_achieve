"""内部 MCP 工具策略注册表。

本模块是 36 个内部 MCP 工具的唯一策略事实源：访问模式、项目绑定、
额度模式、运行模式与 Console 预设。运行时鉴权、Console 密钥页与
开发者契约都从它读取。

与 C 计划分工：C3 拥有 project_api_keys 表扩展（迁移 059）；
C13 拥有客户 MCP；本模块只治理内部 MCP server.py 的工具。
新增工具必须先在这里登记，否则启动测试失败、运行时默认拒绝。
"""

from __future__ import annotations

from dataclasses import dataclass

REGISTRY_VERSION = "n1.v1"


@dataclass(frozen=True, slots=True)
class McpToolPolicy:
    name: str
    access_mode: str  # read | execute | control
    requires_project: bool
    project_scope: str  # bound_project | workspace | operator
    consumes_quota: str  # none | per_call | per_row_worker | per_scheduled_run
    run_mode: str  # sync | async | both | read_only
    cancellable: bool
    preset_groups: tuple[str, ...]


def _p(
    name: str,
    *,
    access_mode: str,
    requires_project: bool = False,
    project_scope: str = "operator",
    consumes_quota: str = "none",
    run_mode: str = "read_only",
    cancellable: bool = False,
    preset_groups: tuple[str, ...] = (),
) -> McpToolPolicy:
    return McpToolPolicy(
        name=name,
        access_mode=access_mode,
        requires_project=requires_project,
        project_scope=project_scope,
        consumes_quota=consumes_quota,
        run_mode=run_mode,
        cancellable=cancellable,
        preset_groups=preset_groups,
    )


_DISCOVERY = ("readonly_discovery", "all")

TIKTOK_EXECUTE_TOOLS: tuple[str, ...] = (
    "tiktok_trend_rank",
    "tiktok_hashtag_videos",
    "tiktok_video_search",
    "tiktok_video_detail",
    "tiktok_video_comments",
    "tiktok_creator_profile",
    "tiktok_creator_search",
    "tiktok_transcript",
    "tiktok_product_search",
    "tiktok_product_detail",
    "tiktok_product_reviews",
    "tiktok_creator_commerce",
    "tiktok_video_products",
    "tiktok_creator_showcase",
    "tiktok_ads_top",
    "tiktok_ads_detail",
)

TOOL_POLICIES: dict[str, McpToolPolicy] = {
    # ── Discovery（只读；不扣额度）────────────────────────────────
    "list_platforms": _p("list_platforms", access_mode="read", preset_groups=_DISCOVERY),
    "list_capabilities": _p("list_capabilities", access_mode="read", preset_groups=_DISCOVERY),
    "describe_capability": _p("describe_capability", access_mode="read", preset_groups=_DISCOVERY),
    "get_playbook": _p("get_playbook", access_mode="read", preset_groups=_DISCOVERY),
    "discover": _p("discover", access_mode="read", preset_groups=_DISCOVERY),
    "inspect": _p("inspect", access_mode="read", preset_groups=_DISCOVERY),
    # ── Run 查询（只读；按 workspace/project 过滤）─────────────────
    "get_run": _p(
        "get_run", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY
    ),
    "list_records": _p(
        "list_records", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY
    ),
    "deep_research_check": _p(
        "deep_research_check",
        access_mode="read",
        project_scope="workspace",
        preset_groups=_DISCOVERY,
    ),
    "enrichment_check": _p(
        "enrichment_check", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY
    ),
    "list_monitors": _p(
        "list_monitors", access_mode="read", project_scope="workspace", preset_groups=_DISCOVERY
    ),
    "balance": _p(
        "balance", access_mode="read", project_scope="bound_project", preset_groups=_DISCOVERY
    ),
    # ── 执行工具（per_call 扣额度）────────────────────────────────
    "collect": _p(
        "collect",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="per_call",
        run_mode="both",
        preset_groups=("tiktok", "all"),
    ),
    "web_search": _p(
        "web_search",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="per_call",
        run_mode="both",
        preset_groups=("search_research", "all"),
    ),
    "web_fetch": _p(
        "web_fetch",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="per_call",
        run_mode="both",
        preset_groups=("search_research", "all"),
    ),
    "answer": _p(
        "answer",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="per_call",
        run_mode="both",
        preset_groups=("search_research", "all"),
    ),
    "deep_research": _p(
        "deep_research",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="per_call",
        run_mode="both",
        preset_groups=("search_research", "all"),
    ),
    "deep_research_start": _p(
        "deep_research_start",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="per_call",
        run_mode="async",
        preset_groups=("search_research", "all"),
    ),
    "workspace_answer": _p(
        "workspace_answer",
        access_mode="execute",
        requires_project=True,
        project_scope="workspace",
        consumes_quota="per_call",
        run_mode="sync",
        preset_groups=("search_research", "all"),
    ),
    "create_monitor": _p(
        "create_monitor",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="per_call",
        run_mode="sync",
        preset_groups=("search_research", "all"),
    ),
    # 报告产物来自本次运行的数据，不再触发外部采集，因此不扣额度。
    "create_report": _p(
        "create_report",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="none",
        run_mode="sync",
        preset_groups=("search_research", "all"),
    ),
    "enrich_list": _p(
        "enrich_list",
        access_mode="execute",
        requires_project=True,
        project_scope="bound_project",
        consumes_quota="per_row_worker",
        run_mode="async",
        preset_groups=("search_research", "all"),
    ),
    **{
        name: _p(
            name,
            access_mode="execute",
            requires_project=True,
            project_scope="bound_project",
            consumes_quota="per_call",
            run_mode="both",
            preset_groups=("tiktok", "all"),
        )
        for name in TIKTOK_EXECUTE_TOOLS
    },
    # ── 控制（不扣额度）────────────────────────────────────────────
    "stop": _p(
        "stop",
        access_mode="control",
        project_scope="workspace",
        run_mode="read_only",
        cancellable=True,
        preset_groups=("ops_query", "all"),
    ),
}

PRESETS: dict[str, tuple[str, ...]] = {
    "readonly_discovery": tuple(
        sorted(name for name, p in TOOL_POLICIES.items() if "readonly_discovery" in p.preset_groups)
    ),
    "search_research": tuple(
        sorted(name for name, p in TOOL_POLICIES.items() if "search_research" in p.preset_groups)
    ),
    "tiktok": tuple(
        sorted(name for name, p in TOOL_POLICIES.items() if "tiktok" in p.preset_groups)
    ),
    "ops_query": tuple(
        sorted(name for name, p in TOOL_POLICIES.items() if "ops_query" in p.preset_groups)
    ),
    "all": tuple(sorted(TOOL_POLICIES)),
}


def get_policy(tool_name: str) -> McpToolPolicy:
    return TOOL_POLICIES[tool_name]
