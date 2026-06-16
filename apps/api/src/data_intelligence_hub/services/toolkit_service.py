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
    ToolkitLecturePlaybookResponse,
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
    lecture_playbooks = _build_lecture_playbooks(intelligence_items)
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
        lecture_playbooks=lecture_playbooks,
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
        method_keywords=(
            "agent",
            "mcp",
            "tool",
            "server",
            "github",
            "cross-platform",
            "compliance",
        ),
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


def _build_lecture_playbooks(
    intelligence_items: list[_TrainingIntelligence],
) -> list[ToolkitLecturePlaybookResponse]:
    return [
        _build_lecture_playbook(item)
        for item in sorted(
            intelligence_items,
            key=lambda intelligence: intelligence.final_score,
            reverse=True,
        )
    ]


def _build_lecture_playbook(item: _TrainingIntelligence) -> ToolkitLecturePlaybookResponse:
    template = _lecture_template(item)
    claim = _summary_value(item.summary, "结论") or item.title
    impact = _summary_value(item.summary, "影响")
    action = _summary_value(item.summary, "建议动作")
    evidence_urls = _source_urls_from_summary(item.summary)
    duration = 25 if item.evidence_count >= 3 else 18
    if template["level"] == "边界":
        duration = max(duration, 20)
    return ToolkitLecturePlaybookResponse(
        id=f"lecture-{item.id}",
        intelligence_id=item.id,
        title=item.title,
        audience=str(template["audience"]),
        level=str(template["level"]),
        duration_minutes=duration,
        claim=claim,
        teaching_sequence=[
            f"问题定位：{claim}",
            f"业务价值：{impact or '把该情报转成培训中的决策判断。'}",
            f"操作主线：{action or '按证据来源完成采集、复核和报告。'}",
            f"证据回溯：现场打开 {item.evidence_count} 条来源，说明原始记录如何进入情报层。",
        ],
        hands_on_steps=list(template["hands_on_steps"]),
        verification_steps=[
            "确认输出包含 source_url、collected_at、raw_record、evidence_url。",
            "确认字段结果能回溯到至少 1 条原始证据。",
            "确认学员能口头说明工具适用场景、失败条件和替代方案。",
        ],
        risk_boundaries=list(template["risk_boundaries"]),
        classroom_exercise=str(template["classroom_exercise"]),
        evidence_urls=evidence_urls,
        evidence_count=item.evidence_count,
        final_score=item.final_score,
    )


def _lecture_template(item: _TrainingIntelligence) -> dict[str, object]:
    text = f"{item.title}\n{item.summary}\n{item.domain}".lower()
    if _has_any(text, ("firecrawl", "crawl4ai", "ai-ready", "markdown")):
        return {
            "audience": "希望把公开网页转成 Markdown/JSON 的 AI 应用与数据采集学员",
            "level": "进阶",
            "hands_on_steps": [
                "选 1 个公开文档页，先用普通 HTTP 抽取正文。",
                "再用 Firecrawl 或 Crawl4AI 输出 Markdown/JSON。",
                "比较标题、正文、链接、字段化结果和失败日志。",
                "把结果登记为 raw record，并关联 evidence URL。",
            ],
            "risk_boundaries": [
                "只处理公开网页和官方文档。",
                "API key、费用和自托管许可必须先确认。",
                "不得绕过登录、验证码或访问控制。",
            ],
            "classroom_exercise": (
                "让学员把同一 URL 分别转成 Markdown 和字段 JSON，"
                "说明哪种结果更适合 RAG 或报告。"
            ),
        }
    if _has_any(text, ("playwright", "browser", "puppeteer", "selenium", "动态页面")):
        return {
            "audience": "需要处理 JS 渲染、点击和页面状态验证的数据采集学员",
            "level": "进阶",
            "hands_on_steps": [
                "用 Playwright 打开公开页面并等待关键元素。",
                "记录 selector、network response、screenshot 和 DOM 字段。",
                "故意制造一次等待失败，复盘 timeout、重试和证据保留。",
                "把浏览器采集和 E2E 测试的边界讲清楚。",
            ],
            "risk_boundaries": [
                "不得模拟恶意流量、绕过验证码或绕过登录限制。",
                "必须设置访问频率、超时和失败预算。",
                "截图证据不得包含敏感个人信息。",
            ],
            "classroom_exercise": (
                "让学员写一个只采公开字段的 Playwright 采集片段，"
                "并提交截图证据。"
            ),
        }
    if _has_any(text, ("scrapy", "python 爬虫", "爬虫工程")):
        return {
            "audience": "需要建立爬虫工程基本功的 Python 学员",
            "level": "入门",
            "hands_on_steps": [
                "创建 Scrapy 项目并定义 spider。",
                "抽取标题、URL、时间等最小字段契约。",
                "通过 pipeline 输出 JSONL。",
                "解释 scheduler、middleware、pipeline 的职责边界。",
            ],
            "risk_boundaries": [
                "必须尊重 robots、限频和公开访问边界。",
                "动态页面不要强行用静态解析硬抓。",
                "不要采集账号态和个人敏感数据。",
            ],
            "classroom_exercise": (
                "让学员用 Scrapy 抽取一个公开列表页，"
                "并画出 spider 到 item pipeline 的流程。"
            ),
        }
    if _has_any(text, ("crawlee", "队列", "状态管理", "生产化")):
        return {
            "audience": "想把单脚本采集升级为任务平台的工程学员",
            "level": "进阶",
            "hands_on_steps": [
                "创建 Crawlee 项目并运行基础 crawler。",
                "加入 request queue、dataset 和失败重试。",
                "对比 CheerioCrawler 与 PlaywrightCrawler 的使用边界。",
                "把运行结果转成可复核的数据集。",
            ],
            "risk_boundaries": [
                "代理、并发和重试必须有成本上限。",
                "不要把平台反爬当成可绕过目标。",
                "任务日志必须保留失败原因。",
            ],
            "classroom_exercise": (
                "让学员把 3 个公开 URL 放入队列，"
                "输出统一字段并解释失败重试策略。"
            ),
        }
    if _has_any(text, ("agent", "mcp", "tool", "browser-use", "工具边界")):
        return {
            "audience": "希望把采集工具接入 AI Agent、Skills 或 MCP 的学员",
            "level": "高阶",
            "hands_on_steps": [
                "先定义一个最小采集工具输入 schema。",
                "设置域名白名单、步数预算和人工复核节点。",
                "让 Agent 调用工具完成公开页面读取或 GitHub API 查询。",
                "导出 tool call trace、结果 JSON 和风险复核记录。",
            ],
            "risk_boundaries": [
                "不要让模型自行决定合规边界。",
                "生产密钥不得暴露给前端或共享配置。",
                "Agent 只能调用白名单工具和白名单域名。",
            ],
            "classroom_exercise": (
                "让学员设计一个 MCP tool schema，"
                "并说明输入校验、输出字段和审计日志。"
            ),
        }
    if _has_any(text, ("github", "topic", "api-first", "repo", "star")):
        return {
            "audience": "需要低风险公开 API 采集样板的数据分析和工程学员",
            "level": "入门",
            "hands_on_steps": [
                "用 GitHub topic 或 repo API 获取公开仓库元数据。",
                "处理分页、rate limit、stars、forks、license、updated_at 字段。",
                "把 repo 元数据写入 raw record。",
                "用 evidence URL 说明每个结论来自哪里。",
            ],
            "risk_boundaries": [
                "只采公开仓库和公开 README。",
                "不采私有仓库、个人邮箱或账号画像。",
                "遵守 GitHub API rate limit。",
            ],
            "classroom_exercise": (
                "让学员用 GitHub API 找出 3 个公开采集工具，"
                "并按 stars 与更新时间排序。"
            ),
        }
    if _has_any(text, ("官方文档", "parser", "release notes", "版本线索")):
        return {
            "audience": "需要把官方文档变成培训材料和监控信号的学员",
            "level": "入门",
            "hands_on_steps": [
                "采集一个官方文档页并保留标题、正文和链接。",
                "拆分 headings、install commands、changelog 线索。",
                "标注 breaking change、版本号或能力变化。",
                "把文档证据挂到对应工具或方法卡。",
            ],
            "risk_boundaries": [
                "只抽取公开文档，不抓账号后台或付费内容。",
                "不要把文档摘要当成法律许可结论。",
                "版本判断必须保留原文链接。",
            ],
            "classroom_exercise": "让学员把一页官方安装文档改写成 SOP，并列出验收命令。",
        }
    if _has_any(text, ("电商", "amazon", "shopify")):
        return {
            "audience": "需要讲跨境电商公开数据采集边界的运营和工程学员",
            "level": "边界",
            "hands_on_steps": [
                "先列出官方 API、自有导出和公开页面三类路径。",
                "定义商品、价格、评论、榜单的字段契约。",
                "标注禁止项：登录态、验证码、批量账号和个人数据。",
                "把合规边界写入方法卡后再讨论采集实现。",
            ],
            "risk_boundaries": [
                "优先官方 API 和自有数据导出。",
                "不提供绕过反爬、验证码和访问控制的步骤。",
                "评论和用户相关数据必须做敏感度评估。",
            ],
            "classroom_exercise": (
                "让学员为 Amazon 或 Shopify 写一张方法卡，"
                "明确字段、来源、限制和禁止项。"
            ),
        }
    if _has_any(text, ("社媒", "youtube", "reddit", "tiktok", "个人级数据")):
        return {
            "audience": "需要讲社媒和内容平台公开趋势采集边界的学员",
            "level": "边界",
            "hands_on_steps": [
                "读取平台官方 API 或开发者政策。",
                "区分聚合趋势、公开视频元数据和个人级数据。",
                "只设计趋势级字段，不设计用户画像字段。",
                "把限制和复核要求写入方法卡。",
            ],
            "risk_boundaries": [
                "不采集个人级画像、私信、登录态内容。",
                "不讲批量账号、绕限流或规避审核。",
                "平台 ToS 和开发者政策必须作为第一证据。",
            ],
            "classroom_exercise": "让学员把一个社媒需求改写成聚合趋势需求，并删除所有个人级字段。",
        }
    if _has_any(text, ("竞品", "公开页面变化", "public site")):
        return {
            "audience": "需要做竞品官网、价格页和文档变更监控的学员",
            "level": "入门",
            "hands_on_steps": [
                "检查 robots.txt、sitemap 和公开页面类型。",
                "采集页面标题、正文摘要、hash 和截图证据。",
                "对比两次快照并生成 diff summary。",
                "把变化挂到竞品实体和报告章节。",
            ],
            "risk_boundaries": [
                "只监控公开页面，不抓账号后台。",
                "必须限速、缓存并记录访问时间。",
                "不要采集未公开接口或受控资源。",
            ],
            "classroom_exercise": "让学员为一个公开价格页设计变更监控字段，并说明告警阈值。",
        }
    if _has_any(text, ("合规", "边界", "禁止项", "审计")):
        return {
            "audience": "需要为采集项目建立授权、频控和审计边界的负责人",
            "level": "边界",
            "hands_on_steps": [
                "为采集需求填写授权范围、公开来源和禁止项。",
                "设置频率限制、数据最小化和审计留痕字段。",
                "把风险边界接入告警和报告。",
                "用一条高风险需求演示如何降级为方法卡。",
            ],
            "risk_boundaries": [
                "没有授权边界就不进入采集实现。",
                "敏感数据、账号态和绕过访问控制默认禁止。",
                "审计记录必须能还原来源、时间和动作。",
            ],
            "classroom_exercise": "让学员审查一条采集需求，标出红线、可采范围和人工审批点。",
        }
    return {
        "audience": "需要理解数据采集工作台证据链的培训学员",
        "level": "入门",
        "hands_on_steps": [
            "阅读情报结论、影响和建议动作。",
            "打开证据 URL 并定位原始事实。",
            "把事实映射到 raw record、entity、signal、intelligence。",
            "复述该情报如何支撑培训决策。",
        ],
        "risk_boundaries": [
            "所有结论必须可回溯到公开证据。",
            "不要把推断包装为事实。",
            "高风险平台只讲方法边界。",
        ],
        "classroom_exercise": "让学员选 1 条情报，画出从原始记录到报告的证据链。",
    }


def _summary_value(summary: str, label: str) -> str | None:
    prefix = f"{label}："
    for line in summary.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip()
    return None


def _source_urls_from_summary(summary: str) -> list[str]:
    value = _summary_value(summary, "来源")
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


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
