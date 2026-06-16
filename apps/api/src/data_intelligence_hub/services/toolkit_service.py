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
    ToolkitAuthorizationChecklistResponse,
    ToolkitBrowserLabResponse,
    ToolkitImageAnchorDiagnosticResponse,
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

IMAGE_ANCHOR_DIAGNOSTICS = (
    ToolkitImageAnchorDiagnosticResponse(
        id="anchor-invisible-playwright",
        image_label="附件 1：invisible_playwright",
        extracted_claim=(
            "截图声称 invisible_playwright 是兼容 Playwright 的 AI 反检测浏览器，"
            "可自动随机固定指纹并通过反爬检测。"
        ),
        source_title="feder-cr/invisible_playwright",
        source_url="https://github.com/feder-cr/invisible_playwright",
        source_type="GitHub repo",
        classification="browser_fingerprint_diagnostics",
        risk_level="high",
        value_judgement=(
            "适合作为浏览器指纹面、自动化可检测性和合规红线的反面教材；"
            "不适合作为绕过 Cloudflare、验证码或访问控制的 SOP。"
        ),
        collection_use=(
            "纳入浏览器解析训练：解释 WebDriver 暴露面、指纹一致性、"
            "截图证据和自有站点 QA 的合法测试边界。"
        ),
        training_takeaway=(
            "凡是以 anti-detect 为核心卖点的工具，只能用于授权测试和风险识别；"
            "培训页必须把它标为高风险。"
        ),
        related_tools=["Playwright", "Firefox", "browser fingerprinting"],
        evidence_urls=[
            "https://github.com/feder-cr/invisible_playwright",
            "https://github.com/feder-cr/invisible_playwright/blob/main/README.md",
        ],
    ),
    ToolkitImageAnchorDiagnosticResponse(
        id="anchor-cloakbrowser",
        image_label="附件 2：CloakBrowser",
        extracted_claim=(
            "截图声称 CloakBrowser 是通过 30 项反爬检测的隐形 Chromium，"
            "可作为 Playwright 替代浏览器。"
        ),
        source_title="CloakHQ/CloakBrowser",
        source_url="https://github.com/CloakHQ/CloakBrowser",
        source_type="GitHub repo",
        classification="stealth_browser_runtime",
        risk_level="high",
        value_judgement=(
            "价值在于提醒采集工程不能只懂 DOM 和 selector，还必须理解浏览器运行时、"
            "TLS/Canvas/WebGL/Client Hints 等检测面。"
        ),
        collection_use=(
            "仅放入“浏览器解析与风控边界”课程，用于讲授权压测、内部风控验证、"
            "可检测性对比和禁止绕过策略。"
        ),
        training_takeaway=(
            "截图中的通过率不是业务许可；来源诊断必须同时记录 license、维护活跃度、"
            "issue 风险和平台 ToS。"
        ),
        related_tools=["Chromium", "Playwright", "Puppeteer"],
        evidence_urls=[
            "https://github.com/CloakHQ/CloakBrowser",
            "https://cloakbrowser.dev/",
        ],
    ),
    ToolkitImageAnchorDiagnosticResponse(
        id="anchor-nanobrowser",
        image_label="附件 3：Nanobrowser",
        extracted_claim=(
            "截图将 Nanobrowser 描述为 Chrome 扩展形态的 AI Web Agent，"
            "强调本地运行、多 Agent 协作和网页任务自动化。"
        ),
        source_title="nanobrowser/nanobrowser",
        source_url="https://github.com/nanobrowser/nanobrowser",
        source_type="GitHub repo / official docs",
        classification="ai_browser_agent",
        risk_level="medium",
        value_judgement=(
            "适合培训 Agent 浏览器的交互模型：规划、导航、校验、人工接管；"
            "风险集中在浏览器权限、凭据暴露、任务越界和结果审计。"
        ),
        collection_use=(
            "归入 Agent / MCP 采集编排：用于讲 Chrome 扩展权限、"
            "本地 LLM/API key、任务轨迹和人工复核。"
        ),
        training_takeaway=(
            "Agent 浏览器不是万能爬虫，必须绑定公开来源、任务预算、"
            "域名白名单和可回放轨迹。"
        ),
        related_tools=["browser-use", "LangChain", "Chrome extension"],
        evidence_urls=[
            "https://github.com/nanobrowser/nanobrowser",
            "https://nanobrowser.ai/docs",
            "https://chromewebstore.google.com/detail/nanobrowser-ai-web-agent/imbddededgmcgfhfpcjmijokokekbkal",
        ],
    ),
    ToolkitImageAnchorDiagnosticResponse(
        id="anchor-agent-reach",
        image_label="附件 4：Agent Reach",
        extracted_claim=(
            "截图声称 Agent Reach 能让 AI Agent 一键获得全网搜索能力，"
            "覆盖 Twitter、Reddit、YouTube、GitHub 等平台且零 API 费用。"
        ),
        source_title="Panniantong/Agent-Reach",
        source_url="https://github.com/Panniantong/Agent-Reach",
        source_type="GitHub repo / skill docs",
        classification="agent_cross_platform_search",
        risk_level="high",
        value_judgement=(
            "训练价值在于多平台 source adapter 与工具健康检查；"
            "高风险点在于平台 ToS、登录态、个人数据和非官方访问路径。"
        ),
        collection_use=(
            "归入 Agent / MCP 与平台 SOP 课程：只讲公开搜索、字段契约、"
            "来源标注和平台政策复核，不讲绕过 API 或访问控制。"
        ),
        training_takeaway=(
            "零 API 费用不等于零合规成本；跨平台 Agent 工具必须先写明授权路径和禁止项。"
        ),
        related_tools=["AI agent skill", "cross-platform search", "GitHub"],
        evidence_urls=[
            "https://github.com/Panniantong/Agent-Reach",
            "https://github.com/Panniantong/Agent-Reach/blob/main/docs/README_en.md",
            "https://allclaw.org/entry/agent-reach",
        ],
    ),
    ToolkitImageAnchorDiagnosticResponse(
        id="anchor-github-tool-map",
        image_label="附件 5：20 个 GitHub 开源工具合集",
        extracted_claim=(
            "截图把采集生态分成 AI 原生、反检测、生产级和专业工具四组，"
            "列出 Firecrawl、Crawl4AI、Stagehand、Hyperbrowser、Scrapling、"
            "Katana、Browserless、Maxun、Heritrix 等候选。"
        ),
        source_title="DamiDefi X article and verified GitHub repositories",
        source_url="https://x.com/DamiDefi/article/2061398246673547296",
        source_type="secondary curation + GitHub repos",
        classification="tool_radar_taxonomy",
        risk_level="medium",
        value_judgement=(
            "二次整理图适合做候选雷达，不适合直接入库为事实；"
            "每个工具必须回到 GitHub、官网或文档做维护度、license、风险和适用场景复核。"
        ),
        collection_use=(
            "归入 GitHub 工具雷达课程：把截图当发现入口，"
            "再用 GitHub API 验证 stars、forks、issues、language、license、updated_at。"
        ),
        training_takeaway=(
            "截图提供 taxonomy，GitHub API 提供事实；课程要训练学员从传播材料回到一手源。"
        ),
        related_tools=[
            "Firecrawl",
            "Crawl4AI",
            "Stagehand",
            "Skyvern",
            "ScrapeGraphAI",
            "AgentQL",
            "Hyperbrowser",
            "Scrapling",
            "Steel",
            "Katana",
            "Browserless",
            "Maxun",
            "Heritrix",
        ],
        evidence_urls=[
            "https://x.com/DamiDefi/article/2061398246673547296",
            "https://github.com/browserbase/stagehand",
            "https://github.com/Skyvern-AI/skyvern",
            "https://github.com/ScrapeGraphAI/Scrapegraph-ai",
            "https://github.com/tinyfish-io/agentql",
            "https://github.com/steel-dev/steel-browser",
            "https://github.com/getmaxun/maxun",
            "https://github.com/projectdiscovery/katana",
            "https://github.com/browserless/browserless",
            "https://github.com/internetarchive/heritrix3",
        ],
    ),
    ToolkitImageAnchorDiagnosticResponse(
        id="anchor-web-check",
        image_label="附件 6：Web-Check",
        extracted_claim=(
            "截图把 Web-Check 描述为能暴露 DNS、服务器架构、技术栈、开放端口、"
            "历史存档和子域名的网站 X-Ray 工具。"
        ),
        source_title="lissy93/web-check",
        source_url="https://github.com/lissy93/web-check",
        source_type="GitHub repo / hosted app",
        classification="osint_site_reconnaissance",
        risk_level="high",
        value_judgement=(
            "对采集工作台很有价值：它不是内容采集器，而是采集前的站点画像、"
            "公开攻击面和合规边界诊断器。"
        ),
        collection_use=(
            "归入公开站点预检课程：只对自有、授权或明确允许分析的网站使用，"
            "输出 DNS、headers、robots、tech stack、security.txt 和公开页面结构。"
        ),
        training_takeaway=(
            "浏览器采集前必须先理解目标站点公开暴露面；"
            "Web-Check 适合做预检，不适合做未授权探测。"
        ),
        related_tools=["OSINT", "DNS", "tech stack detection", "robots.txt"],
        evidence_urls=[
            "https://web-check.xyz/",
            "https://github.com/lissy93/web-check",
            "https://github.com/xray-web/web-check-api",
        ],
    ),
)

BROWSER_LABS = (
    ToolkitBrowserLabResponse(
        id="browser-public-surface-preflight",
        title="公开暴露面预检",
        focus=(
            "在采集前先确认目标站点公开暴露面：robots、sitemap、security.txt、"
            "headers、DNS 和基础技术栈。"
        ),
        risk_level="medium",
        inspection_targets=[
            "robots.txt、sitemap.xml、security.txt",
            "response headers、status code、canonical URL",
            "公开 DNS、证书、重定向链和技术栈线索",
        ],
        playwright_checks=[
            "打开目标首页并记录最终 URL、标题、主要导航和响应状态。",
            "请求 robots.txt 与 sitemap.xml，只记录公开可访问结果。",
            "保存 headers、截图和控制台错误，不做端口扫描或暴力枚举。",
        ],
        evidence_outputs=[
            "preflight JSON",
            "首页截图",
            "headers 快照",
            "robots/sitemap 访问结果",
        ],
        training_task=(
            "选择一个自有或明确授权的网站，完成采集前预检，判断是否进入下一步内容采集。"
        ),
        acceptance_criteria=[
            "能说明目标是否公开可采、是否需要降级为人工复核。",
            "输出包含 URL、时间、headers、robots/sitemap 结论和截图证据。",
            "没有授权时只允许做公开页面读取，不做探测扩展。",
        ],
    ),
    ToolkitBrowserLabResponse(
        id="browser-dom-selector-contract",
        title="DOM 与选择器契约",
        focus=(
            "把网页结构从肉眼浏览转成稳定字段契约，训练 selector、可访问性树、"
            "文本抽取和页面变化监控。"
        ),
        risk_level="low",
        inspection_targets=[
            "标题、主内容、列表项、分页、详情链接",
            "aria role、label、data attribute 和语义化标签",
            "页面 hash、关键字段和空态/异常态",
        ],
        playwright_checks=[
            "用 role/label 优先定位元素，避免脆弱 XPath。",
            "截图并导出最小 DOM 摘要。",
            "模拟一次字段缺失，记录失败原因和替代 selector。",
        ],
        evidence_outputs=[
            "selector contract",
            "字段样例 JSON",
            "DOM 摘要",
            "失败轨迹截图",
        ],
        training_task=(
            "为一个公开列表页写出字段契约，并说明哪些 selector 可长期维护。"
        ),
        acceptance_criteria=[
            "字段能回溯到页面可见内容。",
            "selector 失败时有截图和错误信息。",
            "不依赖登录态、验证码或隐藏接口。",
        ],
    ),
    ToolkitBrowserLabResponse(
        id="browser-network-api-observation",
        title="Network 与公开接口观察",
        focus=(
            "观察浏览器请求、响应、分页和缓存，判断是否存在官方或公开接口优先路径。"
        ),
        risk_level="medium",
        inspection_targets=[
            "document、xhr/fetch、图片和静态资源",
            "分页参数、rate limit header、cache header",
            "公开 API 文档与页面请求之间的字段对应关系",
        ],
        playwright_checks=[
            "监听 response，记录同域公开请求和状态码。",
            "只复核浏览器自然加载产生的请求，不构造隐藏参数枚举。",
            "优先查找官方 API 或导出路径，降低页面抓取成本。",
        ],
        evidence_outputs=[
            "network log",
            "response schema sample",
            "API-first 判断记录",
            "限频与缓存建议",
        ],
        training_task=(
            "打开一个公开文档或 GitHub 页面，找出页面字段和公开 API 字段的对应关系。"
        ),
        acceptance_criteria=[
            "能说明何时优先官方 API，何时才使用浏览器采集。",
            "没有复用未授权 token、cookie 或内部接口。",
            "输出保留 request URL、status、content-type 和字段样例。",
        ],
    ),
    ToolkitBrowserLabResponse(
        id="browser-session-privacy-audit",
        title="会话、Cookie 与隐私审计",
        focus=(
            "理解登录态、Cookie、localStorage、截图和采集结果中的敏感信息风险。"
        ),
        risk_level="high",
        inspection_targets=[
            "Cookie、localStorage、sessionStorage",
            "登录态页面与公开页面的边界",
            "截图中的姓名、邮箱、头像、订单号和 token",
        ],
        playwright_checks=[
            "对公开页面和登录态页面分别记录 storage state 范围。",
            "截图前检查敏感信息，必要时脱敏或只保留结构证据。",
            "不把生产账号态 storage state 作为课程共享素材。",
        ],
        evidence_outputs=[
            "sensitive-field checklist",
            "redacted screenshot",
            "storage scope note",
            "manual review decision",
        ],
        training_task=(
            "把一段登录态采集需求降级为可培训的公开页面或官方导出方案。"
        ),
        acceptance_criteria=[
            "能明确哪些字段禁止进入训练材料。",
            "账号态采集必须有业务授权和人工复核。",
            "任何截图和 JSON 输出都不包含 token、邮箱或个人级数据。",
        ],
    ),
    ToolkitBrowserLabResponse(
        id="browser-fingerprint-risk-diagnostics",
        title="浏览器指纹与反检测风险诊断",
        focus=(
            "用 invisible_playwright、CloakBrowser 等附件锚点解释浏览器指纹、"
            "自动化检测面和合规红线。"
        ),
        risk_level="high",
        inspection_targets=[
            "navigator.webdriver、userAgent、viewport、timezone、locale",
            "Canvas/WebGL/Client Hints/TLS 指纹一致性",
            "反检测工具的 license、维护度、用途声明和风险边界",
        ],
        playwright_checks=[
            "只在自有测试页或授权检测页对比普通浏览器与自动化浏览器差异。",
            "记录检测项名称和差异，不输出绕过配置。",
            "把检测结果归入风险教育，不归入生产采集 SOP。",
        ],
        evidence_outputs=[
            "fingerprint-diff note",
            "risk review",
            "authorized-target proof",
            "do-not-use SOP boundary",
        ],
        training_task=(
            "用附件 1 和附件 2 解释为什么浏览器采集必须理解检测面，但不能把绕过作为课程能力。"
        ),
        acceptance_criteria=[
            "能区分浏览器解析能力、质量验收能力和规避能力。",
            "不提供绕过 Cloudflare、验证码、风控或访问控制的步骤。",
            "高风险工具只能进入授权测试和风险识别课程。",
        ],
    ),
)

AUTHORIZATION_CHECKLISTS = (
    ToolkitAuthorizationChecklistResponse(
        id="auth-public-source",
        title="公开来源采集前检查",
        risk_level="low",
        required_checks=[
            "目标 URL 可匿名访问，内容无需登录或付费。",
            "robots、官方文档或页面声明未禁止目标用途。",
            "字段只包含组织、产品、公开页面内容和公开指标。",
            "已设置频率、缓存、重试和失败预算。",
        ],
        blocked_conditions=[
            "页面要求登录、验证码或绕过访问限制。",
            "字段包含个人邮箱、手机号、私信、订单或账号画像。",
            "采集目的无法落到培训、研究或业务授权场景。",
        ],
        evidence_required=[
            "source_url",
            "collected_at",
            "robots/sitemap 或官方来源说明",
            "截图或原始响应摘要",
        ],
        approval_rule="满足全部必查项且无阻断条件时，可进入低风险采集 SOP。",
    ),
    ToolkitAuthorizationChecklistResponse(
        id="auth-account-session",
        title="账号态或登录态采集检查",
        risk_level="high",
        required_checks=[
            "业务负责人书面确认账号、范围、字段和用途。",
            "优先使用官方 API、自有导出或平台允许的批量导出。",
            "storage state、Cookie、token 不进入代码仓库、截图或培训材料。",
            "结果字段完成数据最小化和敏感信息脱敏。",
        ],
        blocked_conditions=[
            "借用个人账号、批量账号或未授权登录态。",
            "采集私信、订单、支付、个人画像或受保护内容。",
            "需要绕过验证码、风控、速率限制或访问控制。",
        ],
        evidence_required=[
            "授权记录",
            "字段白名单",
            "脱敏样例",
            "人工复核记录",
        ],
        approval_rule="账号态任务默认高风险；缺少授权记录时不得进入实现。",
    ),
    ToolkitAuthorizationChecklistResponse(
        id="auth-platform-policy",
        title="平台政策与 ToS 检查",
        risk_level="high",
        required_checks=[
            "查阅平台开发者政策、API 文档、robots 和 ToS。",
            "区分公开聚合趋势、公开内容元数据和个人级数据。",
            "记录禁止项：绕限流、批量账号、规避审核、二次分发限制。",
            "为课程输出保留政策链接和字段降级说明。",
        ],
        blocked_conditions=[
            "需求以绕过 API 费用、限制或审核为目标。",
            "无法确认数据再使用权或培训展示权。",
            "平台政策明确禁止自动化访问或二次使用。",
        ],
        evidence_required=[
            "policy_url",
            "api_docs_url",
            "blocked_fields",
            "approved_field_contract",
        ],
        approval_rule="平台任务先做政策检查；无法证明允许时，只能讲方法边界，不做采集。",
    ),
)


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
        image_anchor_diagnostics=list(IMAGE_ANCHOR_DIAGNOSTICS),
        browser_labs=list(BROWSER_LABS),
        authorization_checklists=list(AUTHORIZATION_CHECKLISTS),
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
        source_score = _score_tool_source(
            content=content,
            wrapper=wrapper,
            collected_at=record.collected_at,
        )
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
                source_credibility_score=source_score.score,
                source_credibility_level=source_score.level,
                source_credibility_factors=source_score.factors,
            )
        )
    return sorted(tools, key=lambda tool: tool.stars or 0, reverse=True)


@dataclass(frozen=True)
class _SourceCredibilityScore:
    score: int
    level: str
    factors: list[str]


def _score_tool_source(
    *,
    content: dict[str, Any],
    wrapper: dict[str, Any],
    collected_at: datetime,
) -> _SourceCredibilityScore:
    score = 35
    factors: list[str] = ["GitHub API 元数据已采集"]
    source_url = _optional_text(wrapper.get("source_url")) or _optional_text(
        content.get("html_url"),
    )
    if source_url and "github.com/" in source_url:
        score += 15
        factors.append("来源指向官方 GitHub 仓库")

    stars = _optional_int(content.get("stargazers_count")) or 0
    if stars >= 50_000:
        score += 15
        factors.append("社区采用度极高")
    elif stars >= 10_000:
        score += 12
        factors.append("社区采用度高")
    elif stars >= 1_000:
        score += 8
        factors.append("社区采用度可验证")

    if _optional_text(content.get("license")):
        score += 10
        factors.append("license 字段已声明")
    else:
        factors.append("license 字段缺失，培训前需复核")

    updated_at = _optional_datetime(content.get("updated_at"))
    if updated_at is not None:
        age_days = abs((collected_at.replace(tzinfo=None) - updated_at.replace(tzinfo=None)).days)
        if age_days <= 90:
            score += 15
            factors.append("近 90 天仍有更新")
        elif age_days <= 365:
            score += 8
            factors.append("近 1 年仍有更新")
        else:
            factors.append("更新间隔较长，进入课程前需复核维护状态")

    open_issues = _optional_int(content.get("open_issues_count"))
    if open_issues is not None and stars > 0:
        issue_ratio = open_issues / max(stars, 1)
        if issue_ratio <= 0.01:
            score += 5
            factors.append("issue 数量相对社区规模可控")
        elif issue_ratio >= 0.08:
            score -= 5
            factors.append("issue 比例偏高，课程中需标注维护风险")

    score = max(0, min(score, 100))
    if score >= 80:
        level = "high"
    elif score >= 60:
        level = "medium"
    else:
        level = "review"
    return _SourceCredibilityScore(score=score, level=level, factors=factors[:5])


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
