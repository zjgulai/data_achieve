"use client";

import {
  ArrowUpRight,
  BookOpenCheck,
  Bot,
  CheckCircle2,
  Clipboard,
  Copy,
  ExternalLink,
  FileCode2,
  Filter,
  Globe2,
  Layers3,
  PlayCircle,
  Search,
  ShieldAlert,
  Sparkles,
  TerminalSquare,
  Wrench,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { getToolkitOverview } from "@/lib/api/toolkit";
import { cn } from "@/lib/utils";
import type {
  ToolkitLecturePlaybook,
  ToolkitLearningPath,
  ToolkitOverview,
  ToolkitTool,
} from "@/types/toolkit";

import { LecturePlaybookDetail } from "./lecture-playbook-detail";

type CategoryKey =
  | "ai_extraction"
  | "browser_automation"
  | "agent_mcp"
  | "crawler_framework"
  | "platform_method"
  | "governance";
type CategoryFilter = CategoryKey | "all";
type RiskLevel = "low" | "medium" | "high";
type RiskFilter = RiskLevel | "all";
type StageKey = "starter" | "production" | "agent";
type StageFilter = StageKey | "all";

type SourceLink = {
  label: string;
  url: string;
};

type ToolItem = {
  id: string;
  name: string;
  category: CategoryKey;
  stage: StageKey;
  risk: RiskLevel;
  license: string;
  language: string;
  stars: string;
  updatedAt: string;
  tagline: string;
  summary: string;
  trainingUse: string;
  bestFor: string[];
  outputs: string[];
  constraints: string[];
  installCommands: string[];
  verifyCommands: string[];
  sourceLinks: SourceLink[];
};

type PlatformMethod = {
  id: string;
  title: string;
  category: CategoryKey;
  risk: RiskLevel;
  collector: string;
  goal: string;
  sources: string[];
  fieldContract: string[];
  boundary: string;
};

const categoryLabels: Record<CategoryKey, string> = {
  agent_mcp: "Agent / MCP",
  ai_extraction: "AI 抽取",
  browser_automation: "浏览器自动化",
  crawler_framework: "爬虫框架",
  governance: "合规边界",
  platform_method: "平台方法",
};

const categoryIcons: Record<CategoryKey, LucideIcon> = {
  agent_mcp: Bot,
  ai_extraction: Sparkles,
  browser_automation: Globe2,
  crawler_framework: Wrench,
  governance: ShieldAlert,
  platform_method: Layers3,
};

const stageLabels: Record<StageKey, string> = {
  agent: "Agent 编排",
  production: "生产工程",
  starter: "入门实操",
};

const riskLabels: Record<RiskLevel, string> = {
  high: "高风险",
  low: "低风险",
  medium: "中风险",
};

const riskTone: Record<RiskLevel, string> = {
  high: "border-[#F0C9C2] bg-[#FFF5F2] text-[#A04437]",
  low: "border-[#CFE4CF] bg-[#F5FBF3] text-[#44743E]",
  medium: "border-[#F1D9A8] bg-[#FFF9E9] text-[#87611B]",
};

const tools: ToolItem[] = [
  {
    id: "firecrawl",
    name: "Firecrawl",
    category: "ai_extraction",
    stage: "production",
    risk: "medium",
    license: "AGPL-3.0",
    language: "TypeScript",
    stars: "132,972",
    updatedAt: "2026-06-15",
    tagline: "把网页搜索、抓取、交互和结构化输出封装成 API。",
    summary:
      "适合把公开网页转成 Markdown、HTML、结构化 JSON 或 Agent 可消费上下文，培训时用于讲解“API 化采集”和“LLM-ready 数据入口”。",
    trainingUse:
      "先用 Firecrawl 演示从 URL 到清洁文本，再讲 API key、成本、许可、自托管和平台条款边界。",
    bestFor: ["公开网页转 Markdown", "网站地图和批量 crawl", "Agent 通过 MCP 访问网页"],
    outputs: ["markdown", "html", "structured json", "screenshot", "MCP tools"],
    constraints: ["云 API 需要密钥和费用控制", "自托管要评估 AGPL 义务", "不能绕过登录和访问控制"],
    installCommands: [
      "npm install firecrawl",
      "export FIRECRAWL_API_KEY=fc-...",
      "node scripts/collect-firecrawl-page.js",
    ],
    verifyCommands: [
      "node -e \"console.log(process.env.FIRECRAWL_API_KEY ? 'key loaded' : 'missing key')\"",
      "curl -fsS https://docs.firecrawl.dev/llms.txt | head",
    ],
    sourceLinks: [
      { label: "官方文档", url: "https://docs.firecrawl.dev/introduction" },
      { label: "Node SDK", url: "https://docs.firecrawl.dev/sdks/node" },
      { label: "GitHub", url: "https://github.com/firecrawl/firecrawl" },
    ],
  },
  {
    id: "firecrawl-mcp",
    name: "Firecrawl MCP Server",
    category: "agent_mcp",
    stage: "agent",
    risk: "medium",
    license: "MIT",
    language: "JavaScript",
    stars: "6,579",
    updatedAt: "2026-06-15",
    tagline: "把 Firecrawl 变成 Cursor、Claude、VS Code 等 Agent 可调用工具。",
    summary:
      "适合培训 Agent 工具调用：同一个网页采集能力可以通过 MCP 暴露给不同 AI 客户端，降低脚本和 Agent 之间的连接成本。",
    trainingUse:
      "用它说明 MCP 的价值：采集工具不只是脚本，也可以是 Agent 的受控工具入口。",
    bestFor: ["Agent web search", "Agent scrape", "Agent deep research"],
    outputs: ["MCP server", "scrape tool", "search tool", "structured context"],
    constraints: ["仍然需要 Firecrawl API key", "Agent 调用必须设置预算和域名白名单", "生产环境要记录工具调用审计"],
    installCommands: [
      "export FIRECRAWL_API_KEY=fc-...",
      "npx -y firecrawl-mcp",
      "agent-client reload-tools",
    ],
    verifyCommands: [
      "env FIRECRAWL_API_KEY=$FIRECRAWL_API_KEY npx -y firecrawl-mcp --help",
      "node -v",
    ],
    sourceLinks: [
      { label: "MCP Server README", url: "https://github.com/firecrawl/firecrawl-mcp-server" },
      { label: "Firecrawl MCP 指南", url: "https://docs.firecrawl.dev/introduction" },
    ],
  },
  {
    id: "crawl4ai",
    name: "Crawl4AI",
    category: "ai_extraction",
    stage: "starter",
    risk: "low",
    license: "Apache-2.0",
    language: "Python",
    stars: "68,532",
    updatedAt: "2026-06-15",
    tagline: "面向 LLM 的开源网页爬取与 Markdown/JSON 抽取工具。",
    summary:
      "适合把网页变成训练、RAG、报告都可用的结构化内容，能讲清 AsyncWebCrawler、Markdown 生成、CSS 抽取和 LLM 抽取的差异。",
    trainingUse:
      "作为 Python 学员的第一套 AI 采集工具：先跑单页，再扩展到 CSS schema、动态页面和并发。",
    bestFor: ["LLM-ready Markdown", "CSS/XPath 结构化抽取", "动态页面采集"],
    outputs: ["markdown", "fit_markdown", "json", "crawl diagnostics"],
    constraints: ["需要浏览器依赖初始化", "LLM 抽取要单独控制 token 成本", "复杂页面要明确缓存与超时策略"],
    installCommands: [
      "python -m venv .venv",
      "source .venv/bin/activate",
      "pip install crawl4ai",
      "crawl4ai-setup",
    ],
    verifyCommands: ["crawl4ai-doctor", "python -c \"import crawl4ai; print('crawl4ai ready')\""],
    sourceLinks: [
      { label: "安装文档", url: "https://docs.crawl4ai.com/core/installation/" },
      { label: "快速开始", url: "https://docs.crawl4ai.com/core/quickstart/" },
      { label: "GitHub", url: "https://github.com/unclecode/crawl4ai" },
    ],
  },
  {
    id: "browser-use",
    name: "browser-use",
    category: "agent_mcp",
    stage: "agent",
    risk: "medium",
    license: "MIT",
    language: "Python",
    stars: "98,902",
    updatedAt: "2026-06-15",
    tagline: "让 AI Agent 操作真实浏览器，完成网页任务和信息采集。",
    summary:
      "适合讲解“从确定性爬虫到 Agent 浏览器”的边界：Agent 能处理复杂交互，但需要强约束目标、预算、凭据和可审计输出。",
    trainingUse:
      "用于训练复杂网页任务拆解：登录态外的公开任务、页面浏览、点击、提取和报告生成。",
    bestFor: ["AI 浏览器任务", "多步骤网页操作", "需要视觉/DOM 理解的采集"],
    outputs: ["agent trace", "browser actions", "extracted facts", "task report"],
    constraints: ["不要让 Agent 处理敏感个人数据", "生产必须限制域名、步数和费用", "失败重试要保留轨迹"],
    installCommands: [
      "pip install uv",
      "uv venv --python 3.12",
      "source .venv/bin/activate",
      "uv pip install browser-use",
      "uvx browser-use install",
    ],
    verifyCommands: ["python -c \"import browser_use; print('browser-use ready')\"", "uvx browser-use --help"],
    sourceLinks: [
      { label: "快速开始", url: "https://docs.browser-use.com/open-source/quickstart" },
      { label: "GitHub", url: "https://github.com/browser-use/browser-use" },
    ],
  },
  {
    id: "agent-browser",
    name: "agent-browser",
    category: "browser_automation",
    stage: "agent",
    risk: "medium",
    license: "Apache-2.0",
    language: "Rust",
    stars: "36,106",
    updatedAt: "2026-06-15",
    tagline: "面向 AI Agent 的浏览器自动化 CLI，直接暴露 snapshot、click、fill、screenshot。",
    summary:
      "适合训练“命令行驱动浏览器”的采集方式：比完整 Playwright 脚本更轻，比纯 Agent 更可控。",
    trainingUse:
      "用于讲 CLI、可访问性树、页面引用 ref 和截图证据，适合做网页交互采集的可审计流程。",
    bestFor: ["CLI 浏览器控制", "页面 snapshot", "Agent 工具链集成"],
    outputs: ["accessibility tree", "screenshots", "browser action log"],
    constraints: ["需要安装 Chrome for Testing", "复杂任务仍要做状态检查", "不要用于绕过验证码和访问控制"],
    installCommands: [
      "npm install -g agent-browser",
      "agent-browser install",
      "agent-browser open https://scrapy.org",
    ],
    verifyCommands: ["agent-browser snapshot", "agent-browser close"],
    sourceLinks: [
      { label: "GitHub README", url: "https://github.com/vercel-labs/agent-browser" },
      { label: "项目站点", url: "https://agent-browser.dev/" },
    ],
  },
  {
    id: "playwright",
    name: "Playwright",
    category: "browser_automation",
    stage: "production",
    risk: "low",
    license: "Apache-2.0",
    language: "TypeScript",
    stars: "90,991",
    updatedAt: "2026-06-15",
    tagline: "稳定的浏览器自动化和 E2E 测试框架，覆盖 Chromium、Firefox、WebKit。",
    summary:
      "适合作为动态网页采集的底层能力，也适合作为本网站生产验收工具；讲清 selector、等待、截图、网络监听和重试策略。",
    trainingUse:
      "用 Playwright 训练学员建立确定性采集思维：先定位元素，再控制等待，再提取数据，再保存证据。",
    bestFor: ["动态网页采集", "E2E 验收", "截图证据", "CDP 连接"],
    outputs: ["DOM fields", "network responses", "screenshots", "trace"],
    constraints: ["不要模拟恶意流量", "等待策略要显式", "生产采集要加频率和失败预算"],
    installCommands: ["npm init playwright@latest", "npx playwright install chromium"],
    verifyCommands: ["npx playwright --version", "npx playwright test --headed"],
    sourceLinks: [
      { label: "安装文档", url: "https://playwright.dev/docs/intro" },
      { label: "GitHub", url: "https://github.com/microsoft/playwright" },
    ],
  },
  {
    id: "scrapy",
    name: "Scrapy",
    category: "crawler_framework",
    stage: "production",
    risk: "low",
    license: "BSD-3-Clause",
    language: "Python",
    stars: "62,254",
    updatedAt: "2026-06-15",
    tagline: "成熟的 Python 爬虫框架，适合规模化队列、管道、去重和中间件。",
    summary:
      "适合讲解经典爬虫工程：spider、item pipeline、scheduler、middleware、去重、增量和部署。",
    trainingUse:
      "用 Scrapy 做工程基线，让学员理解为什么单脚本采集无法长期维护。",
    bestFor: ["批量网页采集", "增量爬虫", "队列和去重", "数据管道"],
    outputs: ["items", "jsonl", "feed exports", "spider stats"],
    constraints: ["动态页面要配合浏览器方案", "系统依赖要独立虚拟环境", "必须尊重 robots 和频率限制"],
    installCommands: ["python -m venv .venv", "source .venv/bin/activate", "pip install Scrapy", "scrapy startproject training_crawler"],
    verifyCommands: ["scrapy version", "scrapy bench"],
    sourceLinks: [
      { label: "安装文档", url: "https://docs.scrapy.org/en/latest/intro/install.html" },
      { label: "教程", url: "https://docs.scrapy.org/en/latest/intro/tutorial.html" },
      { label: "GitHub", url: "https://github.com/scrapy/scrapy" },
    ],
  },
  {
    id: "crawlee",
    name: "Crawlee",
    category: "crawler_framework",
    stage: "production",
    risk: "low",
    license: "Apache-2.0",
    language: "TypeScript",
    stars: "23,775",
    updatedAt: "2026-06-15",
    tagline: "面向可靠采集的 JS/TS 爬虫库，可接 Cheerio、Playwright、Puppeteer。",
    summary:
      "适合训练 Node.js 采集工程：请求队列、代理、浏览器 crawler、存储和部署到 Actor 平台。",
    trainingUse:
      "作为 JS 技术栈的生产型爬虫入口，解释 HTTP 抓取、浏览器抓取和队列化的取舍。",
    bestFor: ["Node.js 爬虫", "PlaywrightCrawler", "proxy rotation", "Actor 部署"],
    outputs: ["datasets", "request queue", "browser crawler results"],
    constraints: ["浏览器依赖需显式安装", "代理与并发需要成本控制", "平台型部署要明确数据保留策略"],
    installCommands: ["npx crawlee create training-crawler", "cd training-crawler", "npm start"],
    verifyCommands: ["npm test", "npm start"],
    sourceLinks: [
      { label: "快速开始", url: "https://crawlee.dev/js/docs/quick-start" },
      { label: "GitHub", url: "https://github.com/apify/crawlee" },
    ],
  },
  {
    id: "openai-agents-sdk",
    name: "OpenAI Agents SDK",
    category: "agent_mcp",
    stage: "agent",
    risk: "medium",
    license: "MIT",
    language: "Python",
    stars: "27,164",
    updatedAt: "2026-06-15",
    tagline: "用于多 Agent 工作流、工具调用、handoff 和可观测性的轻量框架。",
    summary:
      "适合把采集工具组织成 Agent 工作流：检索、抓取、清洗、判断风险、生成报告，形成可讲解的流水线。",
    trainingUse:
      "用于最后一课：把 Firecrawl、Playwright、GitHub API、数据库写入连接成 Agent 编排。",
    bestFor: ["工具调用编排", "多 Agent 协作", "采集报告生成"],
    outputs: ["tool calls", "agent traces", "handoff states", "structured report"],
    constraints: ["需要 API key 和成本预算", "工具输入输出必须白名单化", "不能让模型决定合规边界"],
    installCommands: ["python -m venv .venv", "source .venv/bin/activate", "pip install openai-agents", "export OPENAI_API_KEY=sk-..."],
    verifyCommands: ["python -c \"import agents; print('agents sdk ready')\""],
    sourceLinks: [
      { label: "快速开始", url: "https://openai.github.io/openai-agents-python/quickstart/" },
      { label: "Agents 指南", url: "https://developers.openai.com/api/docs/guides/agents" },
      { label: "GitHub", url: "https://github.com/openai/openai-agents-python" },
    ],
  },
  {
    id: "mcp-servers",
    name: "MCP Servers",
    category: "agent_mcp",
    stage: "agent",
    risk: "medium",
    license: "按 server 分别确认",
    language: "TypeScript",
    stars: "87,249",
    updatedAt: "2026-06-15",
    tagline: "Model Context Protocol 把外部数据源和工具标准化暴露给 Agent。",
    summary:
      "适合讲 Agent 时代的数据采集接口标准：采集能力从脚本变成可发现、可授权、可审计的工具。",
    trainingUse:
      "用 MCP 解释为什么采集平台要治理工具权限、server 来源、输入 schema 和调用日志。",
    bestFor: ["工具标准化", "跨客户端接入", "Agent 数据源连接"],
    outputs: ["tool schema", "server registry", "agent-accessible actions"],
    constraints: ["必须确认 server 来源和权限", "不要把敏感凭据写入共享配置", "生产要限制可调用工具范围"],
    installCommands: ["node -v", "npx -y @modelcontextprotocol/inspector"],
    verifyCommands: ["npx -y @modelcontextprotocol/inspector --help"],
    sourceLinks: [
      { label: "MCP 介绍", url: "https://modelcontextprotocol.io/docs/getting-started/intro" },
      { label: "Servers 仓库", url: "https://github.com/modelcontextprotocol/servers" },
    ],
  },
];

const repoNameByToolId: Record<string, string> = {
  "agent-browser": "vercel-labs/agent-browser",
  "browser-use": "browser-use/browser-use",
  crawlee: "apify/crawlee",
  crawl4ai: "unclecode/crawl4ai",
  firecrawl: "firecrawl/firecrawl",
  "firecrawl-mcp": "firecrawl/firecrawl-mcp-server",
  "mcp-servers": "modelcontextprotocol/servers",
  "openai-agents-sdk": "openai/openai-agents-python",
  playwright: "microsoft/playwright",
  scrapy: "scrapy/scrapy",
};

const platformMethods: PlatformMethod[] = [
  {
    id: "github-intelligence",
    title: "GitHub 工具雷达",
    category: "platform_method",
    risk: "low",
    collector: "github_repo / github_topic",
    goal: "发现高热度爬虫、Agent、MCP、浏览器自动化工具，并跟踪 stars、issues、更新时间。",
    sources: ["GitHub REST API", "GitHub topics", "仓库 README", "release notes"],
    fieldContract: ["repo", "stars", "forks", "open_issues", "updated_at", "license", "language"],
    boundary: "只采集公开元数据和公开 README，不抓取私有仓库、不采集个人邮箱和账号画像。",
  },
  {
    id: "official-docs-watch",
    title: "官方文档更新监控",
    category: "platform_method",
    risk: "low",
    collector: "generic_web",
    goal: "跟踪工具官方文档、安装命令、能力变化和 breaking change，保证培训材料不过期。",
    sources: ["docs pages", "llms.txt", "changelog", "API reference"],
    fieldContract: ["title", "url", "last_checked_at", "headings", "install_commands", "capability_notes"],
    boundary: "只抽取公开文档，不抓取账号后台、付费内容和受访问控制页面。",
  },
  {
    id: "ecommerce-public-method",
    title: "电商公开信息采集方法",
    category: "platform_method",
    risk: "medium",
    collector: "manual_json / approved_api",
    goal: "沉淀 Amazon、Shopify、独立站公开商品、价格、评论和榜单的合规采集路线。",
    sources: ["官方 API", "公开页面", "站点 sitemap", "商家自有导出"],
    fieldContract: ["platform", "object_type", "public_url", "fields", "rate_limit", "allowed_use"],
    boundary: "优先官方 API 和自有数据导出；不处理绕过反爬、验证码、登录态或受限评论数据。",
  },
  {
    id: "social-public-method",
    title: "社媒与内容平台方法卡",
    category: "platform_method",
    risk: "high",
    collector: "manual_json",
    goal: "把 TikTok、YouTube、Reddit、X 等平台的公开趋势、官方 API、限制和禁止项做成培训卡。",
    sources: ["官方 API 文档", "公开趋势页", "开发者政策", "平台 ToS"],
    fieldContract: ["platform", "approved_paths", "blocked_paths", "data_sensitivity", "review_required"],
    boundary: "不提供登录态采集、个人数据采集、绕过限流或批量账号操作步骤。",
  },
  {
    id: "competitor-site-monitor",
    title: "竞品站点公开变更监控",
    category: "platform_method",
    risk: "medium",
    collector: "generic_web / playwright",
    goal: "监控竞品官网、价格页、文档、招聘页和新闻稿公开变化。",
    sources: ["robots.txt", "sitemap.xml", "pricing page", "docs", "blog"],
    fieldContract: ["url", "page_type", "hash", "changed_at", "diff_summary", "evidence_url"],
    boundary: "遵守 robots、限速和缓存；不抓取账号后台、不绕过访问控制。",
  },
];

const fallbackLearningPaths: ToolkitLearningPath[] = [
  {
    id: "fallback-ecosystem-boundary",
    title: "生态地图与合规边界",
    stage: "starter",
    focus: "先识别工具类别、可采范围、数据敏感度和风险等级。",
    riskLevel: "medium",
    toolCount: 2,
    methodCount: 1,
    intelligenceCount: 0,
    evidenceCount: 0,
    tools: ["GitHub 工具雷达", "MCP Servers", "合规方法卡"],
    methods: ["公开来源识别"],
    acceptanceCriteria: ["学员能判断一个采集需求应该用 API、爬虫、浏览器还是 Agent。"],
    sourceUrls: [],
  },
  {
    id: "fallback-ai-extraction",
    title: "网页到 Markdown/JSON",
    stage: "production",
    focus: "用 Crawl4AI 和 Firecrawl 完成公开网页结构化抽取。",
    riskLevel: "medium",
    toolCount: 2,
    methodCount: 1,
    intelligenceCount: 0,
    evidenceCount: 0,
    tools: ["Crawl4AI", "Firecrawl"],
    methods: ["官方文档监控"],
    acceptanceCriteria: ["输出包含来源 URL、采集时间、正文摘要和字段化结果。"],
    sourceUrls: [],
  },
  {
    id: "fallback-browser-automation",
    title: "动态页面和浏览器采集",
    stage: "production",
    focus: "用 Playwright、Crawlee、agent-browser 处理 JS 渲染与交互。",
    riskLevel: "medium",
    toolCount: 3,
    methodCount: 1,
    intelligenceCount: 0,
    evidenceCount: 0,
    tools: ["Playwright", "Crawlee", "agent-browser"],
    methods: ["公开页面变更监控"],
    acceptanceCriteria: ["保留截图、selector、等待条件和失败原因。"],
    sourceUrls: [],
  },
  {
    id: "fallback-agent-mcp",
    title: "Agent 化采集工作流",
    stage: "agent",
    focus: "把采集工具接入 browser-use、OpenAI Agents SDK 和 MCP。",
    riskLevel: "medium",
    toolCount: 3,
    methodCount: 1,
    intelligenceCount: 0,
    evidenceCount: 0,
    tools: ["browser-use", "OpenAI Agents SDK", "Firecrawl MCP"],
    methods: ["MCP 工具接入"],
    acceptanceCriteria: ["Agent 输出必须有工具调用轨迹、预算限制和人工复核节点。"],
    sourceUrls: [],
  },
  {
    id: "fallback-platform-sop",
    title: "平台方法库沉淀",
    stage: "starter",
    focus: "把 GitHub、电商、社媒、竞品站点抽象成可复用方法卡。",
    riskLevel: "high",
    toolCount: 1,
    methodCount: 4,
    intelligenceCount: 0,
    evidenceCount: 0,
    tools: ["manual_json", "generic_web", "approved_api"],
    methods: ["GitHub", "跨境电商", "社媒", "竞品站点"],
    acceptanceCriteria: ["每张方法卡说明来源、字段、限制、禁止项和培训话术。"],
    sourceUrls: [],
  },
];

const sourceIndex: SourceLink[] = [
  { label: "Crawl4AI Installation", url: "https://docs.crawl4ai.com/core/installation/" },
  { label: "Crawl4AI Quickstart", url: "https://docs.crawl4ai.com/core/quickstart/" },
  { label: "Firecrawl Introduction", url: "https://docs.firecrawl.dev/introduction" },
  { label: "Firecrawl Node SDK", url: "https://docs.firecrawl.dev/sdks/node" },
  { label: "Firecrawl MCP Server", url: "https://github.com/firecrawl/firecrawl-mcp-server" },
  { label: "Browser Use Quickstart", url: "https://docs.browser-use.com/open-source/quickstart" },
  { label: "agent-browser README", url: "https://github.com/vercel-labs/agent-browser" },
  { label: "Crawlee Quick Start", url: "https://crawlee.dev/js/docs/quick-start" },
  { label: "Playwright Installation", url: "https://playwright.dev/docs/intro" },
  { label: "Scrapy Installation", url: "https://docs.scrapy.org/en/latest/intro/install.html" },
  { label: "OpenAI Agents SDK", url: "https://openai.github.io/openai-agents-python/quickstart/" },
  { label: "Model Context Protocol", url: "https://modelcontextprotocol.io/docs/getting-started/intro" },
];

const categoryFilters: Array<{ label: string; value: CategoryFilter }> = [
  { label: "全部", value: "all" },
  { label: "AI 抽取", value: "ai_extraction" },
  { label: "浏览器", value: "browser_automation" },
  { label: "Agent/MCP", value: "agent_mcp" },
  { label: "爬虫框架", value: "crawler_framework" },
  { label: "平台方法", value: "platform_method" },
  { label: "合规", value: "governance" },
];

const riskFilters: Array<{ label: string; value: RiskFilter }> = [
  { label: "全部风险", value: "all" },
  { label: "低风险", value: "low" },
  { label: "中风险", value: "medium" },
  { label: "高风险", value: "high" },
];

const stageFilters: Array<{ label: string; value: StageFilter }> = [
  { label: "全部阶段", value: "all" },
  { label: "入门实操", value: "starter" },
  { label: "生产工程", value: "production" },
  { label: "Agent 编排", value: "agent" },
];

export function ToolkitWorkspace() {
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [stageFilter, setStageFilter] = useState<StageFilter>("all");
  const [selectedToolId, setSelectedToolId] = useState(tools[0]?.id ?? "");
  const [selectedLectureId, setSelectedLectureId] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [toolkitOverview, setToolkitOverview] = useState<ToolkitOverview | null>(null);
  const [toolkitError, setToolkitError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getToolkitOverview()
      .then((overview) => {
        if (mounted) {
          setToolkitOverview(overview);
          setToolkitError(null);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setToolkitOverview(null);
          setToolkitError(caught instanceof Error ? caught.message : "工具库 API 暂不可用");
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const normalizedQuery = query.trim().toLowerCase();
  const dynamicToolByStaticId = useMemo(() => {
    const byName = new Map(toolkitOverview?.tools.map((tool) => [tool.name, tool]) ?? []);
    return new Map(
      Object.entries(repoNameByToolId)
        .map(([toolId, repoName]) => [toolId, byName.get(repoName)] as const)
        .filter((entry): entry is readonly [string, ToolkitTool] => Boolean(entry[1])),
    );
  }, [toolkitOverview?.tools]);
  const visibleMethods = useMemo(
    () => buildVisibleMethods(toolkitOverview),
    [toolkitOverview],
  );
  const learningPaths = useMemo(
    () => toolkitOverview?.learningPaths ?? fallbackLearningPaths,
    [toolkitOverview?.learningPaths],
  );
  const lecturePlaybooks = useMemo(
    () => toolkitOverview?.lecturePlaybooks ?? [],
    [toolkitOverview?.lecturePlaybooks],
  );
  const filteredTools = useMemo(
    () =>
      tools.filter((tool) => {
        const matchesCategory =
          categoryFilter === "all" || tool.category === categoryFilter;
        const matchesRisk = riskFilter === "all" || tool.risk === riskFilter;
        const matchesStage = stageFilter === "all" || tool.stage === stageFilter;
        const searchableText = [
          tool.name,
          tool.tagline,
          tool.summary,
          tool.trainingUse,
          categoryLabels[tool.category],
          stageLabels[tool.stage],
          tool.language,
          tool.license,
          ...tool.bestFor,
          ...tool.outputs,
          ...tool.constraints,
        ]
          .join(" ")
          .toLowerCase();
        const matchesQuery =
          normalizedQuery.length === 0 || searchableText.includes(normalizedQuery);
        return matchesCategory && matchesRisk && matchesStage && matchesQuery;
      }),
    [categoryFilter, normalizedQuery, riskFilter, stageFilter],
  );

  const selectedTool =
    filteredTools.find((tool) => tool.id === selectedToolId) ??
    filteredTools[0] ??
    tools[0];
  const selectedDynamicTool = dynamicToolByStaticId.get(selectedTool.id);
  const SelectedCategoryIcon = categoryIcons[selectedTool.category];
  const filteredMethods = visibleMethods.filter((method) =>
    methodMatchesFilters(method, categoryFilter, riskFilter, normalizedQuery),
  );
  const filteredLearningPaths = learningPaths.filter((path) =>
    learningPathMatchesFilters(path, stageFilter, riskFilter, normalizedQuery),
  );
  const filteredLecturePlaybooks = useMemo(
    () =>
      lecturePlaybooks.filter((playbook) =>
        lecturePlaybookMatchesFilters(playbook, riskFilter, normalizedQuery),
      ),
    [lecturePlaybooks, normalizedQuery, riskFilter],
  );
  const selectedLecture =
    filteredLecturePlaybooks.find((playbook) => playbook.id === selectedLectureId) ??
    filteredLecturePlaybooks[0] ??
    lecturePlaybooks[0];

  useEffect(() => {
    if (
      filteredLecturePlaybooks.length > 0 &&
      !filteredLecturePlaybooks.some((playbook) => playbook.id === selectedLectureId)
    ) {
      setSelectedLectureId(filteredLecturePlaybooks[0].id);
    }
  }, [filteredLecturePlaybooks, selectedLectureId]);

  useEffect(() => {
    if (lecturePlaybooks.length === 0 || typeof window === "undefined") {
      return;
    }
    const lectureId = new URL(window.location.href).searchParams.get("lecture");
    if (lectureId && lecturePlaybooks.some((playbook) => playbook.id === lectureId)) {
      setSelectedLectureId(lectureId);
    }
  }, [lecturePlaybooks]);

  async function copyCommands(id: string, commands: string[]) {
    setCopyError(null);
    try {
      await navigator.clipboard.writeText(commands.join("\n"));
      setCopiedId(id);
      window.setTimeout(() => setCopiedId(null), 1600);
    } catch {
      setCopyError("复制失败，请手动选中命令。");
    }
  }

  function resetFilters() {
    setQuery("");
    setCategoryFilter("all");
    setRiskFilter("all");
    setStageFilter("all");
  }

  function selectLecture(playbookId: string) {
    setSelectedLectureId(playbookId);
    if (typeof window === "undefined") {
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set("lecture", playbookId);
    window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  }

  return (
    <div className="flex min-w-0 max-w-full flex-col gap-6 overflow-hidden">
      <section className="grid min-w-0 max-w-full gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-[#E6D3CE] bg-[#FFF8F6] px-3 py-1 text-xs font-semibold text-[#A24D61]">
                  {toolkitOverview?.generatedAt
                    ? `${formatDate(toolkitOverview.generatedAt)} 核验`
                    : "2026-06-15 核验"}
                </span>
                <span className="rounded-full border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-1 text-xs font-semibold text-[#7A625A]">
                  {toolkitOverview ? "API 已接入" : "本地兜底"}
                </span>
              </div>
              <h2 className="text-2xl font-semibold tracking-normal text-[#1D1D1F]">
                数据采集培训工具与方法库
              </h2>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[#5F5757]">
                这里不是任务日志，而是培训主入口：每个工具都给出适用场景、安装命令、核验命令、输出形态、风险边界和来源链接。
              </p>
            </div>
            <div className="grid min-w-[220px] grid-cols-2 gap-2 text-sm">
              <Metric
                label="训练源"
                value={formatInteger(toolkitOverview?.metrics.sourceCount ?? sourceIndex.length)}
              />
              <Metric
                label="GitHub 工具"
                value={formatInteger(toolkitOverview?.metrics.toolCount ?? tools.length)}
              />
              <Metric
                label="方法卡"
                value={formatInteger(toolkitOverview?.metrics.methodCount ?? platformMethods.length)}
              />
              <Metric
                label="情报证据"
                value={formatInteger(toolkitOverview?.metrics.evidenceCount ?? sourceIndex.length)}
              />
            </div>
          </div>
          {toolkitError ? (
            <p className="mt-4 rounded-xl border border-[#F1D9A8] bg-[#FFF9E9] px-3 py-2 text-xs font-semibold text-[#87611B]">
              {toolkitError}。当前显示已内置的培训 SOP 兜底内容。
            </p>
          ) : null}
        </div>

        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-[#FFFDFC] p-5">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#C25B6E] text-white">
              <BookOpenCheck size={20} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-[#1D1D1F]">培训定位</h3>
              <p className="mt-2 text-sm leading-6 text-[#5F5757]">
                目标不是堆工具名，而是让学员掌握“公开来源识别、工具选择、安装验收、字段契约、风险复核”的完整闭环。
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-4">
        <div className="grid gap-3 xl:grid-cols-[minmax(240px,1fr)_auto] xl:items-center">
          <label className="flex min-w-0 items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-sm text-[#86868B]">
            <Search size={17} aria-hidden="true" />
            <input
              aria-label="搜索采集工具库"
              className="w-full border-0 bg-transparent outline-none"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索 Firecrawl、Crawl4AI、MCP、GitHub、Shopify、SOP"
              type="search"
              value={query}
            />
          </label>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm font-semibold text-[#7A625A] transition hover:bg-[#FBF8F5]"
            onClick={resetFilters}
            type="button"
          >
            <X size={16} aria-hidden="true" />
            清空筛选
          </button>
        </div>

        <div className="mt-4 grid gap-3">
          <FilterRow
            icon={Filter}
            label="分类"
            options={categoryFilters}
            value={categoryFilter}
            onChange={setCategoryFilter}
          />
          <FilterRow
            icon={ShieldAlert}
            label="风险"
            options={riskFilters}
            value={riskFilter}
            onChange={setRiskFilter}
          />
          <FilterRow
            icon={PlayCircle}
            label="阶段"
            options={stageFilters}
            value={stageFilter}
            onChange={setStageFilter}
          />
        </div>
      </section>

      <section className="grid min-w-0 max-w-full gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-[#1D1D1F]">工具雷达</h3>
              <p className="mt-1 text-xs text-[#86868B]">
                当前显示 {filteredTools.length} / {tools.length}
              </p>
            </div>
            <Wrench size={18} className="text-[#C25B6E]" aria-hidden="true" />
          </div>

          {filteredTools.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#E9E5E2] px-4 py-8 text-center text-sm text-[#86868B]">
              没有匹配工具，放宽关键词或筛选条件。
            </div>
          ) : (
            <div className="grid gap-2">
              {filteredTools.map((tool) => {
                const Icon = categoryIcons[tool.category];
                const active = tool.id === selectedTool.id;
                return (
                  <button
                    className={cn(
                      "min-w-0 rounded-xl border px-3 py-3 text-left transition",
                      active
                        ? "border-[#C25B6E] bg-[#FFF8F6] shadow-[0_10px_28px_rgba(194,91,110,0.12)]"
                        : "border-[#EDE6DF] bg-white hover:bg-[#FBF8F5]",
                    )}
                    key={tool.id}
                    onClick={() => setSelectedToolId(tool.id)}
                    type="button"
                  >
                    <div className="flex min-w-0 items-start gap-3">
                      <span
                        className={cn(
                          "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
                          active ? "bg-[#C25B6E] text-white" : "bg-[#FBF8F5] text-[#B47767]",
                        )}
                      >
                        <Icon size={17} aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex min-w-0 flex-wrap items-center gap-2">
                          <span className="truncate text-sm font-semibold text-[#1D1D1F]">
                            {tool.name}
                          </span>
                          <span
                            className={cn(
                              "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                              riskTone[tool.risk],
                            )}
                          >
                            {riskLabels[tool.risk]}
                          </span>
                        </span>
                        <span className="mt-1 block text-xs leading-5 text-[#5F5757]">
                          {tool.tagline}
                        </span>
                        <span className="mt-2 flex flex-wrap gap-2 text-[11px] text-[#86868B]">
                          <span>{categoryLabels[tool.category]}</span>
                          <span>{toolDisplayStars(tool, dynamicToolByStaticId.get(tool.id))} stars</span>
                          <span>{dynamicToolByStaticId.get(tool.id)?.license ?? tool.license}</span>
                        </span>
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#C25B6E] text-white">
                <SelectedCategoryIcon size={20} aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-xl font-semibold text-[#1D1D1F]">
                    {selectedTool.name}
                  </h3>
                  <span
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-xs font-semibold",
                      riskTone[selectedTool.risk],
                    )}
                  >
                    {riskLabels[selectedTool.risk]}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-[#5F5757]">
                  {selectedTool.summary}
                </p>
              </div>
            </div>
            <div className="grid shrink-0 grid-cols-2 gap-2 text-xs">
              <Metric label="Stars" value={toolDisplayStars(selectedTool, selectedDynamicTool)} compact />
              <Metric label="License" value={selectedDynamicTool?.license ?? selectedTool.license} compact />
              <Metric label="Language" value={selectedDynamicTool?.language ?? selectedTool.language} compact />
              <Metric
                label="Updated"
                value={formatDate(selectedDynamicTool?.updatedAt ?? selectedTool.updatedAt)}
                compact
              />
            </div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <InfoBlock title="培训讲法" icon={BookOpenCheck} body={selectedTool.trainingUse} />
            <InfoBlock
              title="适用场景"
              icon={CheckCircle2}
              items={selectedTool.bestFor}
            />
            <InfoBlock title="输出形态" icon={FileCode2} items={selectedTool.outputs} />
            <InfoBlock title="边界限制" icon={ShieldAlert} items={selectedTool.constraints} />
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            <CommandPanel
              commands={selectedTool.installCommands}
              copied={copiedId === `${selectedTool.id}-install`}
              icon={TerminalSquare}
              onCopy={() =>
                void copyCommands(`${selectedTool.id}-install`, selectedTool.installCommands)
              }
              title="安装 SOP"
            />
            <CommandPanel
              commands={selectedTool.verifyCommands}
              copied={copiedId === `${selectedTool.id}-verify`}
              icon={Clipboard}
              onCopy={() =>
                void copyCommands(`${selectedTool.id}-verify`, selectedTool.verifyCommands)
              }
              title="验收命令"
            />
          </div>
          {copyError ? (
            <p className="mt-3 text-xs font-semibold text-[#A04437]">{copyError}</p>
          ) : null}

          <div className="mt-5 border-t border-[#EDE6DF] pt-4">
            <p className="mb-2 text-xs font-semibold uppercase text-[#B47767]">来源</p>
            <div className="flex flex-wrap gap-2">
              {selectedTool.sourceLinks.map((source) => (
                <SourceAnchor key={source.url} source={source} />
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid min-w-0 max-w-full gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-[#1D1D1F]">课堂讲义卡</h3>
              <p className="mt-1 text-xs text-[#86868B]">
                当前显示 {filteredLecturePlaybooks.length} / {lecturePlaybooks.length}
              </p>
            </div>
            <BookOpenCheck size={18} className="text-[#C25B6E]" aria-hidden="true" />
          </div>

          {filteredLecturePlaybooks.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#E9E5E2] px-4 py-8 text-center text-sm text-[#86868B]">
              没有匹配讲义，调整关键词或风险筛选。
            </div>
          ) : (
            <div className="grid gap-2">
              {filteredLecturePlaybooks.map((playbook) => {
                const active = playbook.id === selectedLecture?.id;
                return (
                  <button
                    className={cn(
                      "min-w-0 rounded-xl border px-3 py-3 text-left transition",
                      active
                        ? "border-[#C25B6E] bg-[#FFF8F6] shadow-[0_10px_28px_rgba(194,91,110,0.12)]"
                        : "border-[#EDE6DF] bg-white hover:bg-[#FBF8F5]",
                    )}
                    key={playbook.id}
                    onClick={() => selectLecture(playbook.id)}
                    type="button"
                  >
                    <span className="flex min-w-0 items-start justify-between gap-3">
                      <span className="min-w-0">
                        <span className="line-clamp-2 text-sm font-semibold leading-5 text-[#1D1D1F]">
                          {playbook.title}
                        </span>
                        <span className="mt-2 flex flex-wrap gap-2 text-[11px] text-[#86868B]">
                          <span>{playbook.level}</span>
                          <span>{playbook.durationMinutes} 分钟</span>
                          <span>{playbook.evidenceCount} 条证据</span>
                        </span>
                      </span>
                      <span className="shrink-0 rounded-full border border-[#EDE6DF] bg-white px-2 py-0.5 text-[11px] font-semibold text-[#7A625A]">
                        {Math.round(playbook.finalScore)}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-5">
          {selectedLecture ? (
            <LecturePlaybookDetail
              detailHref={`/toolkit/playbooks/${selectedLecture.id}`}
              playbook={selectedLecture}
              snapshotLabel={`${formatDate(toolkitOverview?.metrics.lastCollectedAt)} 快照`}
            />
          ) : (
            <p className="rounded-xl border border-dashed border-[#E9E5E2] px-3 py-4 text-sm text-[#86868B]">
              API 讲义卡加载后会显示在这里。
            </p>
          )}
        </div>
      </section>

      <section className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-5">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-[#1D1D1F]">平台采集方法卡</h3>
            <p className="mt-1 text-sm text-[#5F5757]">
              训练重点是公开来源、字段契约和禁止边界，不提供规避限制的操作步骤。
            </p>
          </div>
          <span className="text-xs font-semibold text-[#86868B]">
            当前显示 {filteredMethods.length} / {platformMethods.length}
          </span>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          {filteredMethods.map((method) => (
            <article
              className="rounded-xl border border-[#EDE6DF] bg-[#FFFDFC] p-4"
              key={method.id}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-[#EDE6DF] bg-white px-2.5 py-1 text-[11px] font-semibold text-[#7A625A]">
                      {method.collector}
                    </span>
                    <span
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-[11px] font-semibold",
                        riskTone[method.risk],
                      )}
                    >
                      {riskLabels[method.risk]}
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold text-[#1D1D1F]">{method.title}</h4>
                  <p className="mt-2 text-sm leading-6 text-[#5F5757]">{method.goal}</p>
                </div>
                <Layers3 size={18} className="mt-1 shrink-0 text-[#C25B6E]" aria-hidden="true" />
              </div>
              <div className="mt-4 grid gap-3 text-xs text-[#5F5757]">
                <LabeledText label="来源" value={method.sources.join(" / ")} />
                <LabeledText label="字段" value={method.fieldContract.join(" / ")} />
                <LabeledText label="边界" value={method.boundary} />
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="grid min-w-0 max-w-full gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex items-center gap-2">
              <Zap size={18} className="text-[#C25B6E]" aria-hidden="true" />
              <h3 className="text-lg font-semibold text-[#1D1D1F]">培训课程路径</h3>
            </div>
            <span className="text-xs font-semibold text-[#86868B]">
              当前显示 {filteredLearningPaths.length} / {learningPaths.length}
            </span>
          </div>
          <div className="grid gap-3">
            {filteredLearningPaths.map((path, index) => {
              const pathRisk = parseRisk(path.riskLevel);
              const pathStage = parseStage(path.stage);
              return (
                <article
                  className="rounded-xl border border-[#EDE6DF] bg-[#FFFDFC] p-4"
                  key={path.id}
                >
                  <div className="flex gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#FBF8F5] text-sm font-semibold text-[#C25B6E]">
                      {index + 1}
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-semibold text-[#1D1D1F]">
                          {path.title}
                        </h4>
                        <span className="rounded-full border border-[#EDE6DF] bg-white px-2 py-0.5 text-[11px] font-semibold text-[#7A625A]">
                          {stageLabels[pathStage]}
                        </span>
                        <span
                          className={cn(
                            "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
                            riskTone[pathRisk],
                          )}
                        >
                          {riskLabels[pathRisk]}
                        </span>
                      </div>
                      <p className="mt-1 text-sm leading-6 text-[#5F5757]">{path.focus}</p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                        <MiniMetric label="工具" value={path.toolCount} />
                        <MiniMetric label="方法" value={path.methodCount} />
                        <MiniMetric label="情报" value={path.intelligenceCount} />
                        <MiniMetric label="证据" value={path.evidenceCount} />
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {[...path.tools, ...path.methods].slice(0, 8).map((item) => (
                          <span
                            className="rounded-full border border-[#EDE6DF] bg-white px-2.5 py-1 text-[11px] font-semibold text-[#7A625A]"
                            key={`${path.id}-${item}`}
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                      <ul className="mt-3 grid gap-1.5 text-xs leading-5 text-[#86868B]">
                        {path.acceptanceCriteria.map((criterion) => (
                          <li className="flex gap-2" key={criterion}>
                            <CheckCircle2
                              size={14}
                              className="mt-0.5 shrink-0 text-[#6B8E5A]"
                              aria-hidden="true"
                            />
                            <span>{criterion}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </article>
              );
            })}
            {filteredLearningPaths.length === 0 ? (
              <p className="rounded-xl border border-dashed border-[#E9E5E2] px-3 py-4 text-sm text-[#86868B]">
                没有匹配课程路径，放宽阶段、风险或关键词筛选。
              </p>
            ) : null}
          </div>
        </div>

        <div className="min-w-0 max-w-full overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles size={18} className="text-[#C25B6E]" aria-hidden="true" />
            <h3 className="text-lg font-semibold text-[#1D1D1F]">后端情报摘要</h3>
          </div>
          <div className="mb-5 grid gap-3">
            {(toolkitOverview?.intelligenceItems ?? []).slice(0, 4).map((item) => (
              <a
                className="rounded-xl border border-[#EDE6DF] bg-[#FFFDFC] p-3 transition hover:border-[#C25B6E]"
                href={`/intelligence/${item.id}`}
                key={item.id}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold leading-5 text-[#1D1D1F]">{item.title}</p>
                  <span className="shrink-0 rounded-full border border-[#EDE6DF] bg-white px-2 py-0.5 text-[11px] font-semibold text-[#7A625A]">
                    {Math.round(item.finalScore)}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#5F5757]">
                  {extractSummaryLine(item.summary)}
                </p>
                <p className="mt-2 text-[11px] font-semibold text-[#86868B]">
                  {item.evidenceCount} 条证据 · {item.domain}
                </p>
              </a>
            ))}
            {toolkitOverview?.intelligenceItems.length === 0 || !toolkitOverview ? (
              <p className="rounded-xl border border-dashed border-[#E9E5E2] px-3 py-4 text-sm text-[#86868B]">
                API 情报摘要加载后会显示在这里。
              </p>
            ) : null}
          </div>

          <div className="mb-4 flex items-center gap-2">
            <ExternalLink size={18} className="text-[#C25B6E]" aria-hidden="true" />
            <h3 className="text-lg font-semibold text-[#1D1D1F]">来源索引</h3>
          </div>
          <p className="mb-4 text-sm leading-6 text-[#5F5757]">
            本页内容来自官方文档、官方 GitHub 仓库和{" "}
            {formatDate(toolkitOverview?.metrics.lastCollectedAt)} GitHub API 快照；所有指标由增量脚本刷新。
          </p>
          <div className="grid gap-2">
            {sourceIndex.map((source) => (
              <SourceAnchor key={source.url} source={source} wide />
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function Metric({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: string;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2",
        compact ? "min-w-[116px]" : "min-w-0",
      )}
    >
      <p className="text-[11px] font-semibold uppercase text-[#B47767]">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-[#EDE6DF] bg-white px-2 py-1.5">
      <p className="text-[10px] font-semibold uppercase text-[#B47767]">{label}</p>
      <p className="mt-0.5 text-xs font-semibold text-[#1D1D1F]">
        {formatInteger(value)}
      </p>
    </div>
  );
}

function FilterRow<T extends string>({
  icon: Icon,
  label,
  options,
  value,
  onChange,
}: {
  icon: LucideIcon;
  label: string;
  options: Array<{ label: string; value: T }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
      <div className="flex w-20 shrink-0 items-center gap-2 text-xs font-semibold text-[#86868B]">
        <Icon size={15} aria-hidden="true" />
        {label}
      </div>
      <div className="flex min-w-0 flex-wrap gap-2">
        {options.map((option) => (
          <button
            aria-label={`${label}筛选：${option.label}`}
            aria-pressed={option.value === value}
            className={cn(
              "h-9 rounded-xl border px-3 text-xs font-semibold transition",
              option.value === value
                ? "border-[#C25B6E] bg-[#C25B6E] text-white"
                : "border-[#EDE6DF] bg-white text-[#7A625A] hover:bg-[#FBF8F5]",
            )}
            key={option.value}
            onClick={() => onChange(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function InfoBlock({
  title,
  icon: Icon,
  body,
  items,
}: {
  title: string;
  icon: LucideIcon;
  body?: string;
  items?: string[];
}) {
  return (
    <div className="rounded-xl border border-[#EDE6DF] bg-[#FFFDFC] p-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-[#1D1D1F]">
        <Icon size={16} className="text-[#C25B6E]" aria-hidden="true" />
        {title}
      </div>
      {body ? <p className="text-sm leading-6 text-[#5F5757]">{body}</p> : null}
      {items ? (
        <ul className="grid gap-1.5 text-sm text-[#5F5757]">
          {items.map((item) => (
            <li className="flex gap-2" key={item}>
              <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-[#6B8E5A]" aria-hidden="true" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function CommandPanel({
  title,
  icon: Icon,
  commands,
  copied,
  onCopy,
}: {
  title: string;
  icon: LucideIcon;
  commands: string[];
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <div className="rounded-xl border border-[#EDE6DF] bg-[#231A1A] p-4 text-white">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <Icon size={16} className="text-[#F2C4BE]" aria-hidden="true" />
          <h4 className="truncate text-sm font-semibold">{title}</h4>
        </div>
        <button
          className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-white/15 px-2.5 text-xs font-semibold text-[#F7E5DC] transition hover:bg-white/10"
          onClick={onCopy}
          type="button"
        >
          <Copy size={14} aria-hidden="true" />
          {copied ? "已复制" : "复制"}
        </button>
      </div>
      <pre className="max-h-56 overflow-x-auto whitespace-pre-wrap break-words text-xs leading-6 text-[#F7E5DC]">
        {commands.join("\n")}
      </pre>
    </div>
  );
}

function LabeledText({ label, value }: { label: string; value: string }) {
  return (
    <p className="leading-5">
      <span className="font-semibold text-[#1D1D1F]">{label}：</span>
      {value}
    </p>
  );
}

function SourceAnchor({ source, wide = false }: { source: SourceLink; wide?: boolean }) {
  return (
    <a
      className={cn(
        "inline-flex min-w-0 items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#7A625A] transition hover:border-[#C25B6E] hover:text-[#A24D61]",
        wide ? "justify-between" : "",
      )}
      href={source.url}
      rel="noreferrer"
      target="_blank"
    >
      <span className="truncate">{source.label}</span>
      {wide ? (
        <ArrowUpRight size={14} className="shrink-0" aria-hidden="true" />
      ) : (
        <ExternalLink size={13} className="shrink-0" aria-hidden="true" />
      )}
    </a>
  );
}

function buildVisibleMethods(overview: ToolkitOverview | null): PlatformMethod[] {
  if (!overview) {
    return platformMethods;
  }
  return overview.methods.map((method) => ({
    id: method.id,
    title: method.platform ? `${method.platform} 采集方法` : method.title,
    category: parseCategory(method.category),
    risk: parseRisk(method.riskLevel),
    collector: method.recommendedCollector ?? method.collectorType,
    goal:
      method.trainingTakeaway ??
      "沉淀公开来源、字段契约、风险边界和复核口径。",
    sources: method.sourceUrl ? [method.sourceUrl] : [method.collectorType],
    fieldContract:
      method.dataTypes.length > 0
        ? method.dataTypes
        : [method.collectorType, method.category],
    boundary: method.boundary ?? "必须先确认平台公开来源、访问控制和数据敏感度。",
  }));
}

function methodMatchesFilters(
  method: PlatformMethod,
  categoryFilter: CategoryFilter,
  riskFilter: RiskFilter,
  normalizedQuery: string,
) {
  if (categoryFilter !== "all" && method.category !== categoryFilter) {
    return false;
  }
  if (riskFilter !== "all" && method.risk !== riskFilter) {
    return false;
  }
  if (normalizedQuery.length === 0) {
    return true;
  }
  return [
    method.title,
    method.goal,
    method.collector,
    method.boundary,
    ...method.sources,
    ...method.fieldContract,
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalizedQuery);
}

function learningPathMatchesFilters(
  path: ToolkitLearningPath,
  stageFilter: StageFilter,
  riskFilter: RiskFilter,
  normalizedQuery: string,
) {
  if (stageFilter !== "all" && path.stage !== stageFilter) {
    return false;
  }
  const pathRisk = parseRisk(path.riskLevel);
  if (riskFilter !== "all" && pathRisk !== riskFilter) {
    return false;
  }
  if (normalizedQuery.length === 0) {
    return true;
  }
  return [
    path.title,
    path.focus,
    path.stage,
    path.riskLevel,
    ...path.tools,
    ...path.methods,
    ...path.acceptanceCriteria,
    ...path.sourceUrls,
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalizedQuery);
}

function lecturePlaybookMatchesFilters(
  playbook: ToolkitLecturePlaybook,
  riskFilter: RiskFilter,
  normalizedQuery: string,
) {
  if (riskFilter === "high" && playbook.level !== "边界") {
    return false;
  }
  if (riskFilter === "low" && playbook.level === "边界") {
    return false;
  }
  if (normalizedQuery.length === 0) {
    return true;
  }
  return [
    playbook.title,
    playbook.audience,
    playbook.level,
    playbook.claim,
    playbook.classroomExercise,
    ...playbook.teachingSequence,
    ...playbook.handsOnSteps,
    ...playbook.verificationSteps,
    ...playbook.riskBoundaries,
    ...playbook.evidenceUrls,
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalizedQuery);
}

function parseCategory(value: string): CategoryKey {
  return value in categoryLabels ? (value as CategoryKey) : "platform_method";
}

function parseStage(value: string): StageKey {
  return value === "starter" || value === "production" || value === "agent"
    ? value
    : "starter";
}

function parseRisk(value: string): RiskLevel {
  return value === "low" || value === "medium" || value === "high" ? value : "medium";
}

function toolDisplayStars(tool: ToolItem, dynamicTool: ToolkitTool | undefined): string {
  return dynamicTool?.stars != null ? formatInteger(dynamicTool.stars) : tool.stars;
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "未核验";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value.slice(0, 10);
  }
  return parsed.toISOString().slice(0, 10);
}

function extractSummaryLine(summary: string): string {
  return (
    summary
      .split("\n")
      .map((line) => line.trim())
      .find((line) => line.startsWith("结论：")) ?? summary
  ).replace(/^结论：/, "");
}
