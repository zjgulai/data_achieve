from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.intelligence import Evidence, IntelligenceItem
from data_intelligence_hub.models.raw_record import RawRecord
from data_intelligence_hub.schemas.toolkit import (
    ToolkitIntelligenceResponse,
    ToolkitLearningPathResponse,
    ToolkitMethodResponse,
    ToolkitMetricsResponse,
    ToolkitOverviewResponse,
    ToolkitToolResponse,
)

DATASET = "curated_training"
TRAINING_SUMMARY_MARKER = "培训讲解："


async def get_toolkit_overview(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> ToolkitOverviewResponse:
    records = await _list_training_records(session, workspace_id)
    intelligence_items = await _list_training_intelligence(session, workspace_id)
    evidence_count = await _count_training_evidence(session, intelligence_items)
    tools = _build_tools(records)
    methods = _build_methods(records)
    learning_paths = _build_learning_paths(
        tools=tools,
        methods=methods,
        intelligence_items=intelligence_items,
    )
    last_collected_at = max((record.collected_at for record in records), default=None)
    latest_intelligence_at = max(
        (item.updated_at for item in intelligence_items),
        default=None,
    )
    generated_at = max(
        (value for value in (last_collected_at, latest_intelligence_at) if value is not None),
        default=None,
    )

    return ToolkitOverviewResponse(
        dataset=DATASET,
        generated_at=generated_at,
        metrics=ToolkitMetricsResponse(
            source_count=len(records),
            tool_count=len(tools),
            method_count=len(methods),
            intelligence_count=len(intelligence_items),
            evidence_count=evidence_count,
            last_collected_at=last_collected_at,
        ),
        learning_paths=learning_paths,
        tools=tools,
        methods=methods,
        intelligence_items=[
            ToolkitIntelligenceResponse(
                id=item.id,
                title=item.title,
                summary=item.summary,
                domain=item.domain,
                intelligence_type=item.intelligence_type,
                final_score=item.final_score,
                evidence_count=item.evidence_count,
                updated_at=item.updated_at,
            )
            for item in intelligence_items
        ],
    )


async def _list_training_records(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[RawRecord]:
    result = await session.execute(
        select(RawRecord)
        .where(RawRecord.workspace_id == workspace_id)
        .order_by(RawRecord.collected_at.desc())
        .limit(500)
    )
    return [
        record
        for record in result.scalars().all()
        if _is_training_record(record.content)
    ]


class _TrainingIntelligence:
    def __init__(self, item: IntelligenceItem, evidence_count: int) -> None:
        self.id = item.id
        self.title = item.title
        self.summary = item.summary
        self.domain = item.domain
        self.intelligence_type = item.intelligence_type
        self.final_score = item.final_score
        self.evidence_count = evidence_count
        self.updated_at = item.updated_at


async def _list_training_intelligence(
    session: AsyncSession,
    workspace_id: uuid.UUID,
) -> list[_TrainingIntelligence]:
    evidence_counts = (
        select(Evidence.intelligence_id, func.count(Evidence.id).label("evidence_count"))
        .group_by(Evidence.intelligence_id)
        .subquery()
    )
    result = await session.execute(
        select(IntelligenceItem, func.coalesce(evidence_counts.c.evidence_count, 0))
        .outerjoin(evidence_counts, evidence_counts.c.intelligence_id == IntelligenceItem.id)
        .where(
            IntelligenceItem.workspace_id == workspace_id,
            IntelligenceItem.summary.contains(TRAINING_SUMMARY_MARKER),
        )
        .order_by(IntelligenceItem.final_score.desc(), IntelligenceItem.updated_at.desc())
        .limit(24)
    )
    return [
        _TrainingIntelligence(item=item, evidence_count=int(evidence_count))
        for item, evidence_count in result.all()
    ]


async def _count_training_evidence(
    session: AsyncSession,
    intelligence_items: list[_TrainingIntelligence],
) -> int:
    ids = [item.id for item in intelligence_items]
    if not ids:
        return 0
    result = await session.execute(
        select(func.count(Evidence.id)).where(Evidence.intelligence_id.in_(ids))
    )
    return int(result.scalar_one())


def _build_tools(records: list[RawRecord]) -> list[ToolkitToolResponse]:
    tools: list[ToolkitToolResponse] = []
    for record in records:
        wrapper = _record_wrapper(record.content)
        if wrapper.get("collector_type") != "github_repo":
            continue
        content = _content(wrapper)
        full_name = _optional_text(content.get("full_name")) or _optional_text(
            wrapper.get("source_id"),
        )
        if full_name is None:
            continue
        tools.append(
            ToolkitToolResponse(
                id=str(wrapper["source_id"]),
                name=full_name,
                category=str(wrapper.get("category") or "crawler_framework"),
                risk_level=str(wrapper.get("risk_level") or "low"),
                collector_type=str(wrapper.get("collector_type") or "github_repo"),
                source_title=str(wrapper.get("source_title") or full_name),
                source_url=_optional_text(wrapper.get("source_url"))
                or _optional_text(content.get("html_url")),
                description=_optional_text(content.get("description")),
                language=_optional_text(content.get("language")),
                license=_optional_text(content.get("license")),
                stars=_optional_int(content.get("stargazers_count")),
                forks=_optional_int(content.get("forks_count")),
                open_issues=_optional_int(content.get("open_issues_count")),
                updated_at=_optional_datetime(content.get("updated_at")),
                collected_at=record.collected_at,
            )
        )
    return sorted(tools, key=lambda tool: tool.stars or 0, reverse=True)


def _build_methods(records: list[RawRecord]) -> list[ToolkitMethodResponse]:
    methods: list[ToolkitMethodResponse] = []
    for record in records:
        wrapper = _record_wrapper(record.content)
        if wrapper.get("collector_type") != "manual_json":
            continue
        content = _content(wrapper)
        payload = _dict_value(content.get("payload"))
        if payload.get("method_id") is None:
            continue
        method_id = str(payload["method_id"])
        platform = _optional_text(payload.get("platform"))
        methods.append(
            ToolkitMethodResponse(
                id=str(wrapper.get("source_id") or method_id),
                title=str(wrapper.get("source_title") or method_id),
                category=str(wrapper.get("category") or "platform_method"),
                risk_level=str(wrapper.get("risk_level") or "medium"),
                collector_type=str(wrapper.get("collector_type") or "manual_json"),
                source_url=_optional_text(wrapper.get("source_url")),
                platform=platform,
                recommended_collector=_optional_text(payload.get("recommended_collector")),
                data_types=_string_list(payload.get("data_types")),
                boundary=_optional_text(payload.get("boundary")),
                training_takeaway=_optional_text(payload.get("training_takeaway")),
                collected_at=record.collected_at,
            )
        )
    risk_order = {"low": 0, "medium": 1, "high": 2}
    return sorted(methods, key=lambda method: (risk_order.get(method.risk_level, 9), method.title))


@dataclass(frozen=True)
class _LearningPathSpec:
    id: str
    title: str
    stage: str
    focus: str
    risk_level: str
    tool_keywords: tuple[str, ...]
    tool_categories: tuple[str, ...]
    method_keywords: tuple[str, ...]
    intelligence_domains: tuple[str, ...]
    intelligence_keywords: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]


LEARNING_PATH_SPECS = (
    _LearningPathSpec(
        id="github-api-baseline",
        title="GitHub API 公开工具雷达",
        stage="starter",
        focus=(
            "用 GitHub topic、repo API 和公开文档训练低风险采集、"
            "分页、rate limit、字段归一化和证据追溯。"
        ),
        risk_level="low",
        tool_keywords=("github", "scrapy", "crawlee", "crawler", "scraping"),
        tool_categories=("github_intelligence", "crawler_framework"),
        method_keywords=("github", "repo", "topic", "api"),
        intelligence_domains=("osint",),
        intelligence_keywords=("github", "repo", "topic", "star", "release"),
        acceptance_criteria=(
            "能说明公开 repo 元数据和 README 的可采边界。",
            "能输出 repo、stars、forks、license、language、updated_at 字段。",
            "能保留来源 URL、采集时间和证据链接。",
        ),
    ),
    _LearningPathSpec(
        id="ai-extraction-workflow",
        title="AI 抽取与 LLM-ready 内容流",
        stage="production",
        focus=(
            "用 Firecrawl、Crawl4AI、官方文档和 llms.txt 把公开网页转成 "
            "Markdown、JSON 和可复核摘要。"
        ),
        risk_level="medium",
        tool_keywords=("firecrawl", "crawl4ai", "extraction", "markdown", "llm"),
        tool_categories=("ai_extraction",),
        method_keywords=("docs", "llms", "documentation", "官方文档", "文档"),
        intelligence_domains=("osint", "agent"),
        intelligence_keywords=("firecrawl", "crawl4ai", "markdown", "llm", "抽取"),
        acceptance_criteria=(
            "能跑通单页抽取并说明 Markdown 与结构化 JSON 的区别。",
            "能标注 API key、成本、许可和自托管边界。",
            "能把抽取结果关联到原始证据和后续报告。",
        ),
    ),
    _LearningPathSpec(
        id="browser-automation-dynamic-pages",
        title="动态页面与浏览器自动化采集",
        stage="production",
        focus=(
            "用 Playwright、Crawlee、agent-browser 和 browser-use 处理 "
            "JS 渲染、点击、等待、截图和失败轨迹。"
        ),
        risk_level="medium",
        tool_keywords=(
            "playwright",
            "browser",
            "crawlee",
            "puppeteer",
            "agent-browser",
            "browser-use",
        ),
        tool_categories=("browser_automation",),
        method_keywords=("playwright", "generic_web", "sitemap", "变化", "dynamic"),
        intelligence_domains=("osint", "platform"),
        intelligence_keywords=("browser", "playwright", "动态", "网页", "采集"),
        acceptance_criteria=(
            "能解释 selector、等待条件、截图证据和网络响应监听。",
            "能区分公开页面采集和登录态/验证码/访问控制禁止项。",
            "能为失败重试保留可审计轨迹。",
        ),
    ),
    _LearningPathSpec(
        id="agent-mcp-orchestration",
        title="Agent / MCP 采集编排",
        stage="agent",
        focus=(
            "把浏览器、网页抽取、GitHub API 和报告生成封装成 "
            "Agent 可调用、可授权、可审计的工具链。"
        ),
        risk_level="medium",
        tool_keywords=("agent", "mcp", "browser-use", "openai", "firecrawl"),
        tool_categories=("ai_agent_collection", "agent_mcp"),
        method_keywords=("agent", "mcp", "tool", "server"),
        intelligence_domains=("agent",),
        intelligence_keywords=("agent", "mcp", "tool", "browser-use", "编排"),
        acceptance_criteria=(
            "能说明 MCP server、Agent tool 和普通脚本的关系。",
            "能设置域名白名单、步数预算、费用预算和人工复核节点。",
            "能输出工具调用轨迹和结构化采集报告。",
        ),
    ),
    _LearningPathSpec(
        id="platform-sop-governance",
        title="平台 SOP 与合规边界",
        stage="starter",
        focus=(
            "把 GitHub、跨境电商、社媒、视频、内容平台和竞品站点"
            "沉淀成方法卡，先定授权边界再定采集路径。"
        ),
        risk_level="high",
        tool_keywords=("robots", "policy", "tos"),
        tool_categories=("governance",),
        method_keywords=(
            "amazon",
            "shopify",
            "youtube",
            "reddit",
            "tiktok",
            "github",
            "competitor",
            "platform",
            "公开",
            "平台",
        ),
        intelligence_domains=("platform", "governance"),
        intelligence_keywords=("平台", "合规", "robots", "账号", "公开", "边界"),
        acceptance_criteria=(
            "每张方法卡必须写明来源、字段、限制、禁止项和推荐采集器。",
            "高风险平台只能讲官方 API、公开页面和政策边界，不提供规避步骤。",
            "报告中必须保留审计留痕和证据 URL。",
        ),
    ),
)


def _build_learning_paths(
    *,
    tools: list[ToolkitToolResponse],
    methods: list[ToolkitMethodResponse],
    intelligence_items: list[_TrainingIntelligence],
) -> list[ToolkitLearningPathResponse]:
    paths: list[ToolkitLearningPathResponse] = []
    for spec in LEARNING_PATH_SPECS:
        matched_tools = [
            tool
            for tool in tools
            if _matches_tool_path(tool, spec)
        ]
        matched_methods = [
            method
            for method in methods
            if _matches_method_path(method, spec)
        ]
        matched_intelligence = [
            item
            for item in intelligence_items
            if _matches_intelligence_path(item, spec)
        ]
        source_urls = _unique_strings(
            [
                *(tool.source_url for tool in matched_tools),
                *(method.source_url for method in matched_methods),
            ],
        )[:8]

        paths.append(
            ToolkitLearningPathResponse(
                id=spec.id,
                title=spec.title,
                stage=spec.stage,
                focus=spec.focus,
                risk_level=spec.risk_level,
                tool_count=len(matched_tools),
                method_count=len(matched_methods),
                intelligence_count=len(matched_intelligence),
                evidence_count=sum(item.evidence_count for item in matched_intelligence),
                tools=[tool.name for tool in matched_tools[:6]],
                methods=[
                    method.platform or method.title
                    for method in matched_methods[:6]
                ],
                acceptance_criteria=list(spec.acceptance_criteria),
                source_urls=source_urls,
            )
        )
    return paths


def _matches_tool_path(tool: ToolkitToolResponse, spec: _LearningPathSpec) -> bool:
    if tool.category in spec.tool_categories:
        return True
    return _contains_keyword(
        [
            tool.id,
            tool.name,
            tool.category,
            tool.collector_type,
            tool.source_title,
            tool.source_url,
            tool.description,
            tool.language,
        ],
        spec.tool_keywords,
    )


def _matches_method_path(method: ToolkitMethodResponse, spec: _LearningPathSpec) -> bool:
    return _contains_keyword(
        [
            method.id,
            method.title,
            method.category,
            method.collector_type,
            method.source_url,
            method.platform,
            method.recommended_collector,
            method.boundary,
            method.training_takeaway,
            " ".join(method.data_types),
        ],
        spec.method_keywords,
    )


def _matches_intelligence_path(
    item: _TrainingIntelligence,
    spec: _LearningPathSpec,
) -> bool:
    if item.domain in spec.intelligence_domains:
        return True
    return _contains_keyword(
        [
            item.title,
            item.summary,
            item.domain,
            item.intelligence_type,
        ],
        spec.intelligence_keywords,
    )


def _contains_keyword(values: list[str | None], keywords: tuple[str, ...]) -> bool:
    haystack = " ".join(value for value in values if value).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _unique_strings(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _is_training_record(value: dict[str, Any] | list[Any]) -> bool:
    wrapper = _record_wrapper(value)
    provenance = _dict_value(wrapper.get("provenance"))
    return provenance.get("dataset") == DATASET


def _record_wrapper(value: dict[str, Any] | list[Any]) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _content(value: dict[str, Any]) -> dict[str, Any]:
    return _dict_value(value.get("content"))


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _optional_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
