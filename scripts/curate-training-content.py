#!/usr/bin/env python3
# ruff: noqa: E501
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CurationArgs:
    snapshot_path: Path
    output_path: Path
    markdown_path: Path


def parse_args() -> CurationArgs:
    parser = argparse.ArgumentParser(
        description="Curate source-backed training intelligence from a collected snapshot."
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=ROOT_DIR / "tmp" / "outputs" / "training-content-snapshot-20260617.json",
        help="Collected training snapshot JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "tmp" / "outputs" / "training-content-curation-20260617.json",
        help="Machine-readable curation JSON.",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=ROOT_DIR
        / "drafts"
        / "analysis"
        / "analysis-training-content-curation-draft-20260617.md",
        help="Human-readable curation draft.",
    )
    parsed = parser.parse_args()
    return CurationArgs(
        snapshot_path=parsed.snapshot,
        output_path=parsed.output,
        markdown_path=parsed.markdown,
    )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def build_curation(snapshot: dict[str, Any], snapshot_path: Path) -> dict[str, Any]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    records = [record for record in snapshot["records"] if record.get("status") == "ok"]
    entities = build_entities(records)
    signals = build_signals(records)
    intelligence_items = build_intelligence(records, signals, snapshot["generated_at"])
    report = build_report(intelligence_items, snapshot["generated_at"])
    alerts = build_alerts(signals)
    notifications = build_notifications(report, alerts)
    return {
        "dataset": "curated_training",
        "generated_at": generated_at,
        "source_snapshot": str(snapshot_path),
        "snapshot_generated_at": snapshot.get("generated_at"),
        "summary": {
            "source_count": snapshot["summary"]["source_count"],
            "raw_record_count": len(records),
            "entity_count": len(entities),
            "signal_count": len(signals),
            "intelligence_item_count": len(intelligence_items),
            "report_count": 1,
            "alert_count": len(alerts),
            "notification_count": len(notifications),
        },
        "projects": snapshot.get("projects", []),
        "entities": entities,
        "signals": signals,
        "intelligence_items": intelligence_items,
        "report": report,
        "alerts": alerts,
        "notifications": notifications,
    }


def build_entities(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for record in records:
        content = content_of(record)
        record_type = record.get("record_type")
        if record_type == "github_repo":
            name = text_value(content.get("full_name"), record["source_title"])
            entities.append(
                entity(
                    record,
                    entity_type="github_repo",
                    external_id=name,
                    name=name,
                    summary=text_value(content.get("description"), "GitHub repository"),
                    metrics={
                        "stars": content.get("stargazers_count"),
                        "forks": content.get("forks_count"),
                        "open_issues": content.get("open_issues_count"),
                        "updated_at": content.get("updated_at"),
                        "language": content.get("language"),
                    },
                )
            )
        elif record_type == "github_topic":
            topic = text_value(content.get("topic"), record["source_id"])
            entities.append(
                entity(
                    record,
                    entity_type="github_topic",
                    external_id=topic,
                    name=f"GitHub topic: {topic}",
                    summary=f"GitHub topic search with {content.get('total_count')} public repositories.",
                    metrics={
                        "total_count": content.get("total_count"),
                        "top_repository_count": len(content.get("repositories") or []),
                    },
                )
            )
        elif record_type == "generic_web":
            title = text_value(content.get("title"), record["source_title"])
            entities.append(
                entity(
                    record,
                    entity_type="official_doc",
                    external_id=record["source_id"],
                    name=title,
                    summary=text_value(content.get("text_excerpt"), "")[:300],
                    metrics={
                        "text_length": content.get("text_length"),
                        "title": title,
                    },
                )
            )
        elif record_type == "manual_json":
            payload = content.get("payload") if isinstance(content.get("payload"), dict) else {}
            method_id = text_value(payload.get("method_id"), record["source_id"])
            entities.append(
                entity(
                    record,
                    entity_type=text_value(content.get("entity_type"), "platform_method"),
                    external_id=method_id,
                    name=text_value(record.get("source_title"), method_id),
                    summary=text_value(payload.get("training_takeaway"), ""),
                    metrics={
                        "platform": payload.get("platform"),
                        "risk_level": record.get("risk_level"),
                        "recommended_collector": payload.get("recommended_collector"),
                    },
                )
            )
    return entities


def entity(
    record: dict[str, Any],
    entity_type: str,
    external_id: str,
    name: str,
    summary: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"entity-{record['source_id']}",
        "source_id": record["source_id"],
        "raw_record_source_id": record["source_id"],
        "project_key": record.get("project_key"),
        "category": record.get("category"),
        "domain": domain_for_project(text_value(record.get("project_key"), "")),
        "entity_type": entity_type,
        "external_id": external_id,
        "name": name,
        "canonical_url": record.get("source_url"),
        "summary": summary,
        "metrics": metrics,
    }


def build_signals(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repo_records = sorted(
        [record for record in records if record.get("record_type") == "github_repo"],
        key=lambda item: int_value(content_of(item).get("stargazers_count")),
        reverse=True,
    )
    topic_records = sorted(
        [record for record in records if record.get("record_type") == "github_topic"],
        key=lambda item: int_value(content_of(item).get("total_count")),
        reverse=True,
    )
    signals: list[dict[str, Any]] = []
    for record in repo_records[:8]:
        content = content_of(record)
        stars = int_value(content.get("stargazers_count"))
        signals.append(
            {
                "id": f"signal-attention-{record['source_id']}",
                "source_id": record["source_id"],
                "entity_id": f"entity-{record['source_id']}",
                "project_key": record.get("project_key"),
                "signal_type": "attention_level",
                "title": f"{content.get('full_name')} 当前关注度达到 {stars} stars",
                "current_value": stars,
                "previous_value": stars,
                "delta": 0,
                "delta_ratio": 0,
                "confidence": 0.86,
                "severity": "high" if stars >= 50000 else "medium",
                "metadata": {
                    "metric": "stargazers_count",
                    "updated_at": content.get("updated_at"),
                    "source_url": record.get("source_url"),
                    "interpretation": "single_snapshot_attention_level",
                },
            }
        )
    for record in topic_records[:4]:
        content = content_of(record)
        total_count = int_value(content.get("total_count"))
        signals.append(
            {
                "id": f"signal-topic-coverage-{record['source_id']}",
                "source_id": record["source_id"],
                "entity_id": f"entity-{record['source_id']}",
                "project_key": record.get("project_key"),
                "signal_type": "topic_coverage",
                "title": f"{content.get('topic')} topic 当前覆盖 {total_count} 个公开仓库",
                "current_value": total_count,
                "previous_value": total_count,
                "delta": 0,
                "delta_ratio": 0,
                "confidence": 0.82,
                "severity": "medium",
                "metadata": {
                    "metric": "github_topic_total_count",
                    "source_url": record.get("source_url"),
                    "interpretation": "single_snapshot_ecosystem_size",
                },
            }
        )
    compliance_record = first_record(records, "method-compliance-boundary")
    signals.append(
        {
            "id": "signal-risk-method-compliance-boundary",
            "source_id": compliance_record["source_id"],
            "entity_id": f"entity-{compliance_record['source_id']}",
            "project_key": "compliance-boundary",
            "signal_type": "risk_boundary",
            "title": "跨平台采集必须先固化合规边界",
            "current_value": 1,
            "previous_value": 1,
            "delta": 0,
            "delta_ratio": 0,
            "confidence": 0.9,
            "severity": "high",
            "metadata": {
                "metric": "policy_boundary_present",
                "source_url": compliance_record.get("source_url"),
                "interpretation": "governance_required_before_platform_scraping",
            },
        }
    )
    return signals


def build_intelligence(
    records: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    last_checked_at: str,
) -> list[dict[str, Any]]:
    record_map = {record["source_id"]: record for record in records}
    signal_ids = {signal["source_id"]: signal["id"] for signal in signals}

    def repo_stars(source_id: str) -> int:
        return int_value(content_of(record_map[source_id]).get("stargazers_count"))

    def topic_total(source_id: str) -> int:
        return int_value(content_of(record_map[source_id]).get("total_count"))

    items = [
        intelligence(
            "intel-ai-ready-crawling-stack",
            "agent-collection-ecosystem",
            "ai_agent_collection",
            "AI 原生采集工具已形成独立培训模块",
            (
                f"Firecrawl 当前 {repo_stars('github-repo-firecrawl')} stars，"
                f"browser-use 当前 {repo_stars('github-repo-browser-use')} stars，"
                f"Crawl4AI 当前 {repo_stars('github-repo-crawl4ai')} stars；"
                "三者共同说明 AI 应用正在把网页采集、结构化抽取和浏览器操作合并为新的工具层。"
            ),
            "培训中需要把传统爬虫、API 抓取和 AI-ready extraction 分成三条路线讲清楚。",
            "新增一个 20 分钟模块：用 Firecrawl/Crawl4AI/browser-use 对比 API 化抽取、LLM 友好 Markdown、浏览器 agent 三种范式。",
            ["github-repo-firecrawl", "github-repo-browser-use", "github-repo-crawl4ai"],
            signal_ids,
            last_checked_at,
            0.91,
            0.88,
            0.86,
            0.78,
        ),
        intelligence(
            "intel-browser-automation-remains-core",
            "open-source-collection",
            "browser_automation",
            "浏览器自动化仍是动态页面采集的基础能力",
            (
                f"Playwright 当前 {repo_stars('github-repo-playwright')} stars，"
                f"Puppeteer 当前 {repo_stars('github-repo-puppeteer')} stars，"
                f"Selenium 当前 {repo_stars('github-repo-selenium')} stars；"
                "动态渲染、交互触发和端到端验证仍离不开浏览器自动化。"
            ),
            "培训不能只讲 HTTP 请求和 HTML 解析，必须覆盖浏览器自动化的成本、稳定性和合规边界。",
            "把 Playwright 作为主讲工具，Puppeteer/Selenium 作为对比案例，强调页面交互测试和采集不是同一件事。",
            ["github-repo-playwright", "github-repo-puppeteer", "github-repo-selenium", "docs-playwright"],
            signal_ids,
            last_checked_at,
            0.86,
            0.9,
            0.7,
            0.74,
        ),
        intelligence(
            "intel-scrapy-remains-python-baseline",
            "open-source-collection",
            "crawler_framework",
            "Scrapy 仍适合作为 Python 爬虫工程基线",
            (
                f"Scrapy 当前 {repo_stars('github-repo-scrapy')} stars，"
                "且官方 release notes 可采集到完整版本线索；它适合讲解调度、下载、解析、pipeline 和中间件结构。"
            ),
            "Scrapy 的价值不是新奇，而是工程化结构成熟，适合建立学员对爬虫系统边界的基本认识。",
            "保留 Scrapy 作为第一课工程基线，再引入 Crawlee、Playwright 和 AI extraction 作为延伸。",
            ["github-repo-scrapy", "docs-scrapy-news"],
            signal_ids,
            last_checked_at,
            0.78,
            0.88,
            0.55,
            0.6,
        ),
        intelligence(
            "intel-crawlee-bridges-crawler-production-patterns",
            "open-source-collection",
            "crawler_framework",
            "Crawlee 适合讲生产化 crawler 队列和运行抽象",
            (
                f"Crawlee 当前 {repo_stars('github-repo-crawlee')} stars，"
                f"Crawlee Python 当前 {repo_stars('github-repo-crawlee-python')} stars；"
                "它更适合讲请求队列、存储、代理和运行平台抽象。"
            ),
            "相比只讲解析库，Crawlee 更能解释生产采集任务为什么需要队列和状态管理。",
            "把 Crawlee 放在 Scrapy 之后，用作“从脚本到采集任务平台”的过渡案例。",
            ["github-repo-crawlee", "github-repo-crawlee-python", "docs-crawlee"],
            signal_ids,
            last_checked_at,
            0.75,
            0.82,
            0.68,
            0.62,
        ),
        intelligence(
            "intel-agent-frameworks-need-tool-boundaries",
            "agent-collection-ecosystem",
            "ai_agent_collection",
            "Agent 框架要先定义 tool 边界，再谈自动采集",
            (
                f"LangChain 当前 {repo_stars('github-repo-langchain')} stars，"
                f"CrewAI 当前 {repo_stars('github-repo-crewai')} stars；"
                "OpenAI Agents SDK 与 CrewAI Tools 文档也显示 agent 工作流需要明确工具输入、输出和权限边界。"
            ),
            "Agent 能提高编排能力，但不能替代数据授权、采集频率、证据追溯和错误处理。",
            "培训中把 agent 定位为编排层，不把它包装成绕过平台限制的采集器。",
            ["github-repo-langchain", "github-repo-crewai", "docs-openai-agents", "docs-crewai-tools"],
            signal_ids,
            last_checked_at,
            0.83,
            0.84,
            0.8,
            0.7,
        ),
        intelligence(
            "intel-mcp-source-connectors",
            "agent-collection-ecosystem",
            "ai_agent_collection",
            "MCP 适合讲数据源工具化，而不是直接替代采集系统",
            (
                f"MCP servers 当前 {repo_stars('github-repo-mcp-servers')} stars，"
                f"`mcp-server` topic 当前覆盖 {topic_total('github-topic-mcp-server')} 个公开仓库；"
                "这说明工具协议和数据源连接器正在成为 agent 工作台的重要接口层。"
            ),
            "MCP 的培训重点应放在授权、工具 schema、审计和可观测性，而不是把所有数据源直接暴露给模型。",
            "新增 MCP 章节：演示如何把已授权数据源封装为工具，同时保留 evidence trail。",
            ["github-repo-mcp-servers", "github-topic-mcp-server", "docs-mcp-intro"],
            signal_ids,
            last_checked_at,
            0.82,
            0.83,
            0.82,
            0.66,
        ),
        intelligence(
            "intel-agent-browser-understanding",
            "agent-collection-ecosystem",
            "ai_agent_collection",
            "Agent 浏览器训练要把页面理解、网络观察和人工复核连成闭环",
            (
                f"agent-browser 当前 {repo_stars('github-repo-agent-browser')} stars，"
                f"Stagehand 当前 {repo_stars('github-repo-stagehand')} stars，"
                f"browser-use 当前 {repo_stars('github-repo-browser-use')} stars；"
                "三者共同说明 Agent 采集训练不能只讲自然语言指令，还要讲浏览器快照、网络请求、截图证据和人工接管。"
            ),
            "浏览器 Agent 的业务价值在于帮助学员理解页面，而不是把网页自动化包装成无边界抓取。",
            "新增 agent-browser 课堂练习：打开授权页面，导出 accessibility snapshot、network 摘要、截图和页面 diff，再写成方法卡。",
            [
                "github-repo-agent-browser",
                "github-repo-stagehand",
                "github-repo-browser-use",
                "method-agent-browser-browser-qa",
            ],
            signal_ids,
            last_checked_at,
            0.86,
            0.86,
            0.82,
            0.76,
        ),
        intelligence(
            "intel-ai-extraction-pipeline-diversifies",
            "agent-collection-ecosystem",
            "ai_agent_collection",
            "AI 抽取工具已从 crawler 扩展到语义查询、视觉流程和 graph pipeline",
            (
                f"ScrapeGraphAI 当前 {repo_stars('github-repo-scrapegraphai')} stars，"
                f"Skyvern 当前 {repo_stars('github-repo-skyvern')} stars，"
                f"AgentQL 当前 {repo_stars('github-repo-agentql')} stars；"
                "AI 采集工具正在分化为 prompt pipeline、视觉浏览器流程和语义查询三类训练材料。"
            ),
            "培训不能只把 AI 采集等同于 Firecrawl 或 Crawl4AI，需要让学员知道不同工具的控制粒度和失败模式。",
            "把 ScrapeGraphAI、Skyvern、AgentQL 放入对比表：分别讲结构化抽取、工作流自动化和语义定位。",
            ["github-repo-scrapegraphai", "github-repo-skyvern", "github-repo-agentql"],
            signal_ids,
            last_checked_at,
            0.82,
            0.82,
            0.84,
            0.68,
        ),
        intelligence(
            "intel-rpa-no-code-collection-track",
            "rpa-no-code-collection",
            "rpa_automation",
            "RPA 和 no-code 采集应成为业务培训主线，而不是开发者工具的附录",
            "Browse AI、Octoparse、影刀 RPA、Power Automate 和 UiPath 的来源与方法卡已经覆盖从点选式网页抽取到企业 RPA 治理的完整梯度。",
            "培训对象不全是工程师；业务用户需要看见网页字段、流程录制、定时运行、导出和异常复核这些可操作 SOP。",
            "新增 RPA/no-code 训练路径：先用 Browse AI 或 Octoparse 讲字段建模，再用影刀 RPA 讲国内后台流程，最后用 Power Automate/UiPath 讲企业治理。",
            [
                "docs-browse-ai",
                "docs-octoparse",
                "docs-yingdao-rpa",
                "method-browse-ai-no-code",
                "method-yingdao-rpa",
                "method-power-automate-desktop",
                "method-uipath-studio",
            ],
            signal_ids,
            last_checked_at,
            0.84,
            0.82,
            0.78,
            0.74,
        ),
        intelligence(
            "intel-open-source-no-code-bridges-training",
            "rpa-no-code-collection",
            "no_code_scraping",
            "开源 no-code 采集平台能连接业务培训和工程化采集",
            (
                f"Maxun 当前 {repo_stars('github-repo-maxun')} stars，"
                "Apify 平台文档和 Actor 方法卡提供了从可视化任务到平台化运行、数据集和 API 导出的训练路径。"
            ),
            "no-code 不等于低质量；它适合先训练字段建模和任务边界，再过渡到 Crawlee、Actor 和自建采集服务。",
            "把 Maxun 与 Apify 放在同一模块：Maxun 讲开源可视化采集，Apify 讲平台化 Actor 和数据集交付。",
            ["github-repo-maxun", "docs-apify-platform", "method-apify-actor-platform"],
            signal_ids,
            last_checked_at,
            0.78,
            0.8,
            0.78,
            0.66,
        ),
        intelligence(
            "intel-browser-preflight-before-scraping",
            "browser-preflight-risk",
            "osint_preflight",
            "浏览器采集前必须先做公开暴露面和授权范围预检",
            (
                f"Web-Check 当前 {repo_stars('github-repo-web-check')} stars，"
                f"Katana 当前 {repo_stars('github-repo-katana')} stars，"
                f"httpx 当前 {repo_stars('github-repo-httpx')} stars；"
                "这些工具说明采集工作台需要先理解目标站点公开暴露面、URL 范围和 HTTP 信号，再进入内容采集。"
            ),
            "站点预检能降低误采、过采和越权风险，是培训和生产采集之间的关键控制点。",
            "新增预检训练：对自有或授权站点输出 DNS/headers/robots/URL 范围/截图证据，并明确是否允许进入下一步采集。",
            [
                "github-repo-web-check",
                "github-repo-katana",
                "github-repo-httpx",
                "method-web-check-preflight",
                "method-katana-authorized-crawl",
            ],
            signal_ids,
            last_checked_at,
            0.86,
            0.84,
            0.8,
            0.82,
        ),
        intelligence(
            "intel-fingerprint-risk-is-training-boundary",
            "browser-preflight-risk",
            "browser_risk",
            "浏览器指纹和反检测工具只能作为风险教育，不应进入绕过式 SOP",
            (
                f"Scrapling 当前 {repo_stars('github-repo-scrapling')} stars，"
                f"Pydoll 当前 {repo_stars('github-repo-pydoll')} stars；"
                "它们具备浏览器解析、CDP、HAR 或自适应抽取训练价值，但 anti-bot/stealth 相关语义会显著提高合规风险。"
            ),
            "课程需要帮助学员理解检测面，但不能训练绕过 Cloudflare、DataDome、Kasada、验证码、登录控制或平台风控。",
            "把 Pydoll、Scrapling 和浏览器指纹边界放入高风险案例区：只讲授权测试、差异诊断和禁止项。",
            [
                "github-repo-scrapling",
                "github-repo-pydoll",
                "method-browser-fingerprint-boundary",
            ],
            signal_ids,
            last_checked_at,
            0.82,
            0.82,
            0.86,
            0.9,
        ),
        intelligence(
            "intel-github-api-first-low-risk",
            "platform-methods",
            "platform_method",
            "GitHub 适合作为低风险 API-first 采集训练样板",
            (
                f"`web-scraping` topic 当前覆盖 {topic_total('github-topic-web-scraping')} 个公开仓库，"
                f"`ai-agent` topic 当前覆盖 {topic_total('github-topic-ai-agent')} 个公开仓库；"
                "GitHub REST 文档和 repo API 文档可以支撑从官方 API 获取公开元数据。"
            ),
            "GitHub 能同时训练 API 请求、分页、rate limit、数据归一化和证据追溯，是最适合公开教学的起点。",
            "把 GitHub repo/topic 作为第一轮实操数据源，避免一开始进入高风险平台页面抓取。",
            ["github-topic-web-scraping", "github-topic-ai-agent", "docs-github-rest", "docs-github-repos"],
            signal_ids,
            last_checked_at,
            0.88,
            0.92,
            0.62,
            0.82,
        ),
        intelligence(
            "intel-official-docs-need-parser-strategy",
            "platform-methods",
            "platform_method",
            "官方文档采集要区分标题、正文摘要和版本线索",
            "本轮快照显示 GitHub repo API 与 Scrapy release notes 正文较长，通用 HTML 抽取足以发现内容，但培训级情报需要进一步做章节化解析。",
            "只抓全文会制造噪音；面向培训的文档采集需要稳定标题、更新时间、章节和关键声明。",
            "后续实现 doc-specific parser，把 release notes、API reference 和 guide 文档拆成不同模板。",
            ["docs-github-repos", "docs-scrapy-news", "docs-openai-agents"],
            signal_ids,
            last_checked_at,
            0.7,
            0.8,
            0.72,
            0.58,
        ),
        intelligence(
            "intel-ecommerce-method-boundary",
            "platform-methods",
            "platform_method",
            "电商平台训练先讲合规方法卡，不直接讲绕过式抓取",
            "Amazon 与 Shopify 相关方法卡明确把公开页面、授权导出、合规 provider 和数据最小化放在前置位置。",
            "电商采集很容易滑向反爬绕过、价格监控滥用和平台规则冲突；培训必须先建立边界。",
            "把电商章节定义为方法设计课：字段目标、授权来源、频率控制、证据留存和风险提示。",
            ["method-amazon-public-pages", "method-shopify-storefront"],
            signal_ids,
            last_checked_at,
            0.76,
            0.86,
            0.58,
            0.8,
        ),
        intelligence(
            "intel-social-collection-aggregate-only",
            "platform-methods",
            "platform_method",
            "社媒采集训练应聚焦聚合趋势，不暴露个人级数据",
            "Reddit、YouTube、TikTok 方法卡都把公开聚合信号、官方 API 或公开趋势页作为训练边界。",
            "社媒数据的主要风险是个人信息、画像和平台政策；训练中要避免教个人级抓取。",
            "社媒章节只讲公开趋势、聚合指标和内容主题，不讲账号画像、私信、登录态或规避限制。",
            ["method-reddit-public-api", "method-youtube-data-api", "method-tiktok-creative-center"],
            signal_ids,
            last_checked_at,
            0.78,
            0.88,
            0.62,
            0.84,
        ),
        intelligence(
            "intel-competitor-public-site-monitoring",
            "platform-methods",
            "platform_method",
            "竞品监控应从公开页面变化检测开始",
            "竞品 public site 方法卡把 landing page、pricing page 和 feature page 作为可讲解目标，同时要求尊重 robots 和频率边界。",
            "公开页面变化检测能支撑商业培训场景，又比高风险平台数据抓取更容易闭环。",
            "用 generic_web 采集公开页面，形成 raw record、entity snapshot、page_changed signal 和 evidence。",
            ["method-competitor-public-site", "docs-playwright"],
            signal_ids,
            last_checked_at,
            0.73,
            0.82,
            0.6,
            0.62,
        ),
        intelligence(
            "intel-compliance-as-first-class-intelligence",
            "compliance-boundary",
            "compliance_boundary",
            "合规边界必须成为工作台的一等情报对象",
            "跨平台合规方法卡明确禁止绕过登录、付费墙、访问控制或在无合法基础时采集个人信息。",
            "如果合规只写在文档里，采集任务和 agent 编排会绕过它；工作台必须把风险边界呈现在 alerts 和 intelligence 页面。",
            "把 high risk 方法卡生成 alert，并在每个高风险平台方法情报中引用该边界。",
            ["method-compliance-boundary"],
            signal_ids,
            last_checked_at,
            0.9,
            0.92,
            0.7,
            0.9,
        ),
        intelligence(
            "intel-topic-map-guides-training-priority",
            "open-source-collection",
            "github_intelligence",
            "GitHub topic 覆盖量可用于安排培训优先级",
            (
                f"`mcp-server` topic 当前覆盖 {topic_total('github-topic-mcp-server')} 个仓库，"
                f"`ai-agent` topic 当前覆盖 {topic_total('github-topic-ai-agent')} 个仓库，"
                f"`web-scraping` topic 当前覆盖 {topic_total('github-topic-web-scraping')} 个仓库；"
                "topic 覆盖量可作为培训内容排序的弱信号。"
            ),
            "topic 数量不能代表质量，但能提示哪些生态需要优先解释概念和工具差异。",
            "把 topic 覆盖量用于 dashboard 概览，不直接作为推荐排名的唯一依据。",
            ["github-topic-mcp-server", "github-topic-ai-agent", "github-topic-web-scraping"],
            signal_ids,
            last_checked_at,
            0.72,
            0.76,
            0.66,
            0.58,
        ),
        intelligence(
            "intel-raw-evidence-trail-is-training-asset",
            "platform-methods",
            "platform_method",
            "原始记录和 evidence trail 本身就是培训资产",
            "本轮 44 个 source 均已成功生成 raw record，且每条记录都有 source URL、collector type 和 collected_at。",
            "培训中要让学员看到从 source 到 raw record、entity、signal、intelligence、report 的完整链路。",
            "在页面验收时逐页展示同一条情报如何回溯到 GitHub/API/docs/method card 来源。",
            ["docs-github-rest", "github-repo-scrapy", "method-github-public-api"],
            signal_ids,
            last_checked_at,
            0.82,
            0.86,
            0.56,
            0.72,
        ),
    ]
    return items


def intelligence(
    item_id: str,
    project_key: str,
    category: str,
    title: str,
    claim: str,
    impact: str,
    recommended_action: str,
    evidence_source_ids: list[str],
    signal_ids_by_source: dict[str, str],
    last_checked_at: str,
    impact_score: float,
    confidence_score: float,
    novelty_score: float,
    urgency_score: float,
) -> dict[str, Any]:
    final_score = round(
        impact_score * 0.35 + confidence_score * 0.25 + novelty_score * 0.2 + urgency_score * 0.2,
        3,
    )
    return {
        "id": item_id,
        "project_key": project_key,
        "category": category,
        "domain": domain_for_project(project_key),
        "title": title,
        "claim": claim,
        "impact": impact,
        "recommended_action": recommended_action,
        "training_talk_track": f"讲解重点：{impact} 动作：{recommended_action}",
        "evidence_source_ids": evidence_source_ids,
        "evidence_urls": [source_url_for(source_id) for source_id in evidence_source_ids],
        "entity_ids": [f"entity-{source_id}" for source_id in evidence_source_ids],
        "signal_ids": [
            signal_ids_by_source[source_id]
            for source_id in evidence_source_ids
            if source_id in signal_ids_by_source
        ],
        "last_checked_at": last_checked_at,
        "intelligence_type": "opportunity" if category != "compliance_boundary" else "risk",
        "status": "new",
        "scores": {
            "impact": impact_score,
            "confidence": confidence_score,
            "novelty": novelty_score,
            "urgency": urgency_score,
            "final": final_score,
        },
    }


def build_report(intelligence_items: list[dict[str, Any]], last_checked_at: str) -> dict[str, Any]:
    top_items = sorted(
        intelligence_items,
        key=lambda item: item["scores"]["final"],
        reverse=True,
    )[:6]
    report_date = last_checked_at[:10]
    return {
        "id": "report-training-intelligence-weekly-20260617",
        "title": "数据采集培训情报周报",
        "report_type": "weekly_training",
        "status": "published",
        "period_start": report_date,
        "period_end": report_date,
        "last_checked_at": last_checked_at,
        "summary": "本周培训内容聚焦 GitHub API、开源爬虫框架、浏览器自动化、AI agent、RPA/no-code、站点预检和跨平台合规边界。",
        "sections": [
            {
                "title": "优先讲解",
                "items": [item["title"] for item in top_items],
            },
            {
                "title": "工具生态",
                "items": [
                    item["title"]
                    for item in intelligence_items
                    if item["category"]
                    in {
                        "crawler_framework",
                        "browser_automation",
                        "ai_agent_collection",
                        "no_code_scraping",
                    }
                ][:6],
            },
            {
                "title": "业务流程与合规",
                "items": [
                    item["title"]
                    for item in intelligence_items
                    if item["category"]
                    in {
                        "platform_method",
                        "compliance_boundary",
                        "rpa_automation",
                        "osint_preflight",
                        "browser_risk",
                    }
                ][:6],
            },
        ],
        "intelligence_ids": [item["id"] for item in intelligence_items],
    }


def build_alerts(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    high_signals = [signal for signal in signals if signal["severity"] == "high"]
    return [
        {
            "id": "alert-ai-agent-tool-attention",
            "title": "AI 采集工具关注度较高",
            "severity": "high",
            "status": "open",
            "signal_ids": [
                signal["id"]
                for signal in high_signals
                if signal["project_key"] == "agent-collection-ecosystem"
            ][:3],
            "recommended_action": "在培训中优先展示 Firecrawl、browser-use、Crawl4AI 和 MCP 的差异。",
        },
        {
            "id": "alert-browser-automation-core",
            "title": "浏览器自动化仍是动态页面采集核心能力",
            "severity": "medium",
            "status": "open",
            "signal_ids": [
                signal["id"]
                for signal in high_signals
                if signal["source_id"] in {"github-repo-playwright", "github-repo-puppeteer"}
            ],
            "recommended_action": "保留 Playwright 章节，并把采集与 E2E 测试边界讲清楚。",
        },
        {
            "id": "alert-compliance-boundary-required",
            "title": "高风险平台采集必须先讲合规边界",
            "severity": "high",
            "status": "open",
            "signal_ids": ["signal-risk-method-compliance-boundary"],
            "recommended_action": "电商、社媒和竞品章节必须先展示禁止项和授权边界。",
        },
    ]


def build_notifications(report: dict[str, Any], alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": "notification-training-report-ready",
            "type": "report_ready",
            "title": "数据采集培训情报周报已生成",
            "message": report["summary"],
            "target_id": report["id"],
        },
        {
            "id": "notification-training-alerts-ready",
            "type": "alerts_ready",
            "title": "培训告警已生成",
            "message": f"已生成 {len(alerts)} 条培训相关告警。",
            "target_id": alerts[0]["id"],
        },
        {
            "id": "notification-training-evidence-ready",
            "type": "evidence_ready",
            "title": "培训证据链已就绪",
            "message": "GitHub、官方文档和方法卡快照已可用于页面讲解。",
            "target_id": report["id"],
        },
    ]


def write_markdown(curation: dict[str, Any], path: Path) -> None:
    document_date = date_from_snapshot_path(curation) or str(curation["generated_at"])[:10]
    lines = [
        "---",
        "title: 培训内容情报萃取草稿",
        "doc_type: analysis",
        "module: operations",
        "topic: training-content-curation",
        "status: draft",
        f"created: {document_date}",
        f"updated: {document_date}",
        "owner: self",
        "source: human+ai",
        "---",
        "",
        "# 培训内容情报萃取草稿",
        "",
        "## 摘要",
        "",
        f"- source snapshot: `{curation['source_snapshot']}`",
        f"- raw records: {curation['summary']['raw_record_count']}",
        f"- entities: {curation['summary']['entity_count']}",
        f"- signals: {curation['summary']['signal_count']}",
        f"- intelligence items: {curation['summary']['intelligence_item_count']}",
        "",
        "## 情报清单",
        "",
        "| ID | 标题 | 分类 | 证据数 | Final Score |",
        "|---|---|---|---:|---:|",
    ]
    for item in curation["intelligence_items"]:
        lines.append(
            "| "
            f"`{item['id']}` | {item['title']} | `{item['category']}` | "
            f"{len(item['evidence_source_ids'])} | {item['scores']['final']} |"
        )
    lines.extend(
        [
            "",
            "## 验收备注",
            "",
            "1. 本草稿只用于审阅萃取结果，不代表生产已写库。",
            "2. 所有“当前”判断来自快照文件中的 `last_checked_at`。",
            "3. 高风险平台只保留方法边界，不包含绕过访问控制的操作细节。",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def date_from_snapshot_path(curation: dict[str, Any]) -> str | None:
    name = Path(str(curation.get("source_snapshot") or "")).stem
    suffix = name.rsplit("-", maxsplit=1)[-1]
    if len(suffix) == 8 and suffix.isdigit():
        return f"{suffix[:4]}-{suffix[4:6]}-{suffix[6:]}"
    return None


def write_json(value: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def first_record(records: list[dict[str, Any]], source_id: str) -> dict[str, Any]:
    for record in records:
        if record.get("source_id") == source_id:
            return record
    raise ValueError(f"record not found: {source_id}")


def content_of(record: dict[str, Any]) -> dict[str, Any]:
    content = record.get("content")
    return content if isinstance(content, dict) else {}


def source_url_for(source_id: str) -> str:
    if source_id.startswith("github-topic-"):
        return f"https://github.com/topics/{source_id.removeprefix('github-topic-')}"
    if source_id.startswith("github-repo-"):
        repo_urls = {
            "github-repo-scrapy": "https://github.com/scrapy/scrapy",
            "github-repo-playwright": "https://github.com/microsoft/playwright",
            "github-repo-puppeteer": "https://github.com/puppeteer/puppeteer",
            "github-repo-selenium": "https://github.com/SeleniumHQ/selenium",
            "github-repo-crawlee": "https://github.com/apify/crawlee",
            "github-repo-crawlee-python": "https://github.com/apify/crawlee-python",
            "github-repo-crawl4ai": "https://github.com/unclecode/crawl4ai",
            "github-repo-firecrawl": "https://github.com/firecrawl/firecrawl",
            "github-repo-browser-use": "https://github.com/browser-use/browser-use",
            "github-repo-openai-agents-python": "https://github.com/openai/openai-agents-python",
            "github-repo-openai-agents-js": "https://github.com/openai/openai-agents-js",
            "github-repo-crewai": "https://github.com/crewAIInc/crewAI",
            "github-repo-crewai-tools": "https://github.com/crewAIInc/crewAI-tools",
            "github-repo-mcp-servers": "https://github.com/modelcontextprotocol/servers",
            "github-repo-stagehand": "https://github.com/browserbase/stagehand",
            "github-repo-langchain": "https://github.com/langchain-ai/langchain",
            "github-repo-skyvern": "https://github.com/Skyvern-AI/skyvern",
            "github-repo-scrapegraphai": "https://github.com/ScrapeGraphAI/Scrapegraph-ai",
            "github-repo-agentql": "https://github.com/tinyfish-io/agentql",
            "github-repo-agent-browser": "https://github.com/vercel-labs/agent-browser",
            "github-repo-maxun": "https://github.com/getmaxun/maxun",
            "github-repo-web-check": "https://github.com/lissy93/web-check",
            "github-repo-katana": "https://github.com/projectdiscovery/katana",
            "github-repo-httpx": "https://github.com/projectdiscovery/httpx",
            "github-repo-pydoll": "https://github.com/autoscrape-labs/pydoll",
            "github-repo-scrapling": "https://github.com/D4Vinci/Scrapling",
            "github-repo-browserless": "https://github.com/browserless/browserless",
        }
        return repo_urls[source_id]
    doc_urls = {
        "docs-github-rest": "https://docs.github.com/en/rest",
        "docs-github-repos": "https://docs.github.com/rest/repos/repos",
        "docs-scrapy-news": "https://docs.scrapy.org/en/latest/news.html",
        "docs-playwright": "https://playwright.dev/",
        "docs-crawlee": "https://crawlee.dev/",
        "docs-crawl4ai": "https://docs.crawl4ai.com/",
        "docs-firecrawl": "https://docs.firecrawl.dev/api-reference/v2-introduction",
        "docs-openai-agents": "https://developers.openai.com/api/docs/guides/agents",
        "docs-crewai-tools": "https://docs.crewai.com/en/concepts/tools",
        "docs-mcp-intro": "https://modelcontextprotocol.io/docs/getting-started/intro",
        "docs-browse-ai": "https://www.browse.ai/",
        "docs-octoparse": "https://www.octoparse.com/",
        "docs-yingdao-rpa": "https://www.yingdao.com/",
        "docs-power-automate-web-automation": "https://learn.microsoft.com/en-us/power-automate/desktop-flows/actions-reference/webautomation",
        "docs-uipath-studio": "https://docs.uipath.com/studio/standalone/2024.10/user-guide/introduction",
        "docs-apify-platform": "https://docs.apify.com/platform",
        "docs-browserless": "https://docs.browserless.io/",
        "method-github-public-api": "https://docs.github.com/en/rest",
        "method-amazon-public-pages": "https://www.amazon.com/",
        "method-shopify-storefront": "https://www.shopify.com/",
        "method-reddit-public-api": "https://www.reddit.com/dev/api/",
        "method-youtube-data-api": "https://developers.google.com/youtube/v3",
        "method-tiktok-creative-center": "https://ads.tiktok.com/business/creativecenter/",
        "method-competitor-public-site": "https://www.w3.org/TR/robots/",
        "method-compliance-boundary": "https://www.w3.org/TR/robots/",
        "method-browse-ai-no-code": "https://www.browse.ai/",
        "method-octoparse-no-code": "https://www.octoparse.com/",
        "method-yingdao-rpa": "https://www.yingdao.com/",
        "method-power-automate-desktop": "https://learn.microsoft.com/en-us/power-automate/desktop-flows/actions-reference/webautomation",
        "method-uipath-studio": "https://docs.uipath.com/studio/standalone/2024.10/user-guide/introduction",
        "method-apify-actor-platform": "https://docs.apify.com/platform",
        "method-web-check-preflight": "https://web-check.xyz/",
        "method-katana-authorized-crawl": "https://github.com/projectdiscovery/katana",
        "method-agent-browser-browser-qa": "https://github.com/vercel-labs/agent-browser",
        "method-browser-fingerprint-boundary": "https://www.w3.org/TR/robots/",
    }
    return doc_urls[source_id]


def text_value(value: Any, fallback: str) -> str:
    return value if isinstance(value, str) and value.strip() else fallback


def int_value(value: Any) -> int:
    return value if isinstance(value, int) else 0


def domain_for_project(project_key: str) -> str:
    return {
        "open-source-collection": "osint",
        "platform-methods": "platform",
        "agent-collection-ecosystem": "agent",
        "compliance-boundary": "governance",
        "rpa-no-code-collection": "rpa",
        "browser-preflight-risk": "browser",
    }.get(project_key, "training")


def main() -> int:
    args = parse_args()
    snapshot = load_json(args.snapshot_path)
    curation = build_curation(snapshot, args.snapshot_path)
    write_json(curation, args.output_path)
    write_markdown(curation, args.markdown_path)
    print(
        "curation_written="
        f"{args.output_path} "
        f"markdown_written={args.markdown_path} "
        f"intelligence_items={curation['summary']['intelligence_item_count']} "
        f"entities={curation['summary']['entity_count']} "
        f"signals={curation['summary']['signal_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
