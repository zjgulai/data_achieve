from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from data_intelligence_hub.models.collector import Collector
from data_intelligence_hub.repositories.collectors import get_collector_by_type, list_collectors


@dataclass(frozen=True)
class CollectorDefinition:
    type: str
    name: str
    description: str
    config_schema: dict[str, Any]


COLLECTOR_CATALOG: tuple[CollectorDefinition, ...] = (
    CollectorDefinition(
        type="github_repo",
        name="GitHub Repo",
        description="Monitor a public GitHub repository.",
        config_schema={
            "required": ["owner", "repo"],
            "properties": {"owner": "string", "repo": "string"},
        },
    ),
    CollectorDefinition(
        type="github_topic",
        name="GitHub Topic",
        description="Discover public repositories by GitHub topic.",
        config_schema={
            "required": ["topic"],
            "properties": {"topic": "string", "max_results": "integer"},
        },
    ),
    CollectorDefinition(
        type="generic_web",
        name="Generic Web Page",
        description="Monitor a single public web page.",
        config_schema={
            "required": ["url"],
            "properties": {"url": "string", "extract_mode": "string"},
        },
    ),
    CollectorDefinition(
        type="public_feed",
        name="Public RSS/Atom Feed",
        description="Monitor a public RSS or Atom feed.",
        config_schema={
            "required": ["url"],
            "properties": {"url": "string", "feed_type": "string", "max_items": "integer"},
        },
    ),
    CollectorDefinition(
        type="manual_json",
        name="Manual JSON",
        description="Import structured JSON payloads manually.",
        config_schema={
            "required": ["entity_type", "json_data"],
            "properties": {"entity_type": "string", "json_data": "object"},
        },
    ),
    CollectorDefinition(
        type="ecommerce_product_discovery",
        name="Ecommerce Product Discovery",
        description="Discover product URLs from a public independent-site listing or sitemap page.",
        config_schema={
            "required": ["url"],
            "properties": {
                "url": "string",
                "max_products": "integer",
                "platform_hint": "string",
            },
        },
    ),
    CollectorDefinition(
        type="ecommerce_product_page",
        name="Ecommerce Product Page",
        description="Parse a public independent-site product page into structured product fields.",
        config_schema={
            "required": ["url"],
            "properties": {
                "url": "string",
                "fields": "array",
                "platform_hint": "string",
            },
        },
    ),
    CollectorDefinition(
        type="tikhub_social",
        name="TikHub Social",
        description="Collect TikTok / Instagram / Xiaohongshu data via TikHub REST API.",
        config_schema={
            "required": ["endpoint_type"],
            "properties": {
                "endpoint_type": "string",
                "keyword": "string",
                "unique_id": "string",
                "ch_id": "string",
                "user_id": "string",
                "max_items": "integer",
            },
        },
    ),
    CollectorDefinition(
        type="apify_actor",
        name="Apify Actor",
        description="Run any Apify Actor and collect Dataset items.",
        config_schema={
            "required": ["actor_id", "actor_input"],
            "properties": {
                "actor_id": "string",
                "actor_input": "object",
                "max_items": "integer",
                "max_total_charge_usd": "number",
                "run_timeout_seconds": "integer",
            },
        },
    ),
    CollectorDefinition(
        type="playwright_browser",
        name="Playwright Browser",
        description="Headless Chromium browser collector for JS-rendered pages.",
        config_schema={
            "required": ["url"],
            "properties": {
                "url": "string",
                "wait_for": "string",
                "extract_mode": "string",
                "wait_selector": "string",
            },
        },
    ),
    CollectorDefinition(
        type="anysearch",
        name="AnySearch",
        description="Search the web via AnySearch API and collect structured results.",
        config_schema={
            "required": ["query"],
            "properties": {
                "query": "string",
                "site": "string",
                "num_results": "integer",
            },
        },
    ),
    CollectorDefinition(
        type="jina_reader",
        name="Jina Reader",
        description="Convert any public web page to clean Markdown via r.jina.ai.",
        config_schema={
            "required": ["url"],
            "properties": {
                "url": "string",
                "return_format": "string",
            },
        },
    ),
    CollectorDefinition(
        type="sherlock",
        name="Sherlock Username Search",
        description="Search for a username across 400+ social networks via sherlock-project CLI.",
        config_schema={
            "required": ["username"],
            "properties": {"username": "string", "sites": "array"},
        },
    ),
    CollectorDefinition(
        type="maigret",
        name="Maigret Username Dossier",
        description="Build a cross-platform dossier from a username via maigret (3000+ sites).",
        config_schema={
            "required": ["username"],
            "properties": {"username": "string", "max_sites": "integer"},
        },
    ),
    CollectorDefinition(
        type="twscrape_search",
        name="X/Twitter Search",
        description="Search X/Twitter for tweets matching a query via twscrape.",
        config_schema={
            "required": ["query"],
            "properties": {"query": "string", "limit": "integer", "product": "string"},
        },
    ),
    CollectorDefinition(
        type="twscrape_user_tweets",
        name="X/Twitter User Timeline",
        description="Fetch the public timeline of an X/Twitter user via twscrape.",
        config_schema={
            "required": ["username"],
            "properties": {"username": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="twscrape_trends",
        name="X/Twitter Trending Topics",
        description="Fetch X/Twitter trending topics for a given category via twscrape.",
        config_schema={"required": [], "properties": {"category": "string"}},
    ),
    CollectorDefinition(
        type="anydoc_file_to_markdown",
        name="Document to Markdown",
        description="Convert a remote document file (PDF, DOCX, PPTX, etc.) to Markdown.",
        config_schema={
            "required": ["file_url"],
            "properties": {"file_url": "string", "file_type": "string"},
         },
    ),
    CollectorDefinition(
        type="bilibili_video_search",
        name="B站视频搜索",
        description="按关键词搜索 B站视频内容。",
        config_schema={"required": ["keyword"], "properties": {"keyword": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="bilibili_video_info",
        name="Bilibili 视频信息",
        description="获取 B站单个视频的元数据、播放量、评论等。",
        config_schema={"required": ["bvid"], "properties": {"bvid": "string"}},
    ),
    CollectorDefinition(
        type="bilibili_user_videos",
        name="Bilibili UP主视频列表",
        description="获取 B站 UP主的视频列表。",
        config_schema={
            "required": ["uid"],
            "properties": {"uid": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="bilibili_video_comments",
        name="Bilibili 视频评论",
        description="获取 B站视频的评论列表。",
        config_schema={
            "required": ["bvid"],
            "properties": {"bvid": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="weibo_keyword_search",
        name="微博关键词搜索",
        description="搜索微博关键词，返回相关帖子。",
        config_schema={
            "required": ["keyword"],
            "properties": {"keyword": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="weibo_user_posts",
        name="微博用户帖子",
        description="获取微博用户的帖子列表。",
        config_schema={
            "required": ["user_id"],
            "properties": {"user_id": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="weibo_trending_topics",
        name="微博热搜榜",
        description="获取微博当前热搜话题列表。",
        config_schema={"required": [], "properties": {}},
    ),
    CollectorDefinition(
        type="zhihu_question_answers",
        name="知乎问题回答",
        description="获取知乎问题下的回答列表。",
        config_schema={
            "required": ["question_id"],
            "properties": {"question_id": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="zhihu_keyword_search",
        name="知乎关键词搜索",
        description="搜索知乎关键词，返回相关内容。",
        config_schema={
            "required": ["keyword"],
            "properties": {"keyword": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="zhihu_hot_list",
        name="知乎热榜",
        description="获取知乎当前热榜话题。",
        config_schema={"required": [], "properties": {}},
    ),
    CollectorDefinition(
        type="baidu_search",
        name="百度搜索",
        description="通过 MediaCrawler 采集百度搜索结果。",
        config_schema={
            "required": ["query"],
            "properties": {"query": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="bing_search",
        name="Bing 搜索",
        description="通过 MediaCrawler 采集 Bing 搜索结果。",
        config_schema={
            "required": ["query"],
            "properties": {"query": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="duckduckgo_search",
        name="DuckDuckGo 搜索",
        description="通过 MediaCrawler 采集 DuckDuckGo 搜索结果。",
        config_schema={
            "required": ["query"],
            "properties": {"query": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="kuaishou_video_search",
        name="快手视频搜索",
        description="搜索快手关键词视频。",
        config_schema={
            "required": ["keyword"],
            "properties": {"keyword": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="kuaishou_user_videos",
        name="快手用户视频",
        description="获取快手用户的视频列表。",
        config_schema={
            "required": ["user_id"],
            "properties": {"user_id": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="firecrawl_crawl",
        name="Firecrawl 全站采集",
        description="通过 Firecrawl 对目标网站进行全站结构化采集。",
        config_schema={
            "required": ["url"],
            "properties": {"url": "string", "max_pages": "integer"},
        },
    ),
    CollectorDefinition(
        type="firecrawl_extract",
        name="Firecrawl 结构化提取",
        description="通过 Firecrawl 从页面提取结构化数据。",
        config_schema={"required": ["url"], "properties": {"url": "string", "schema": "object"}},
    ),
    CollectorDefinition(
        type="firecrawl_batch_scrape",
        name="Firecrawl 批量抓取",
        description="通过 Firecrawl 批量抓取多个 URL。",
        config_schema={"required": ["urls"], "properties": {"urls": "array"}},
    ),
    CollectorDefinition(
        type="devto_articles",
        name="Dev.to 文章",
        description="采集 Dev.to 技术文章。",
        config_schema={"required": [], "properties": {"tag": "string", "limit": "integer"}},
    ),
    CollectorDefinition(
        type="juejin_articles",
        name="掘金文章",
        description="采集掘金技术文章。",
        config_schema={
            "required": [],
            "properties": {"category": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="substack_posts",
        name="Substack 文章",
        description="采集 Substack Newsletter 文章。",
        config_schema={
            "required": ["publication_url"],
            "properties": {"publication_url": "string", "limit": "integer"},
        },
    ),
    CollectorDefinition(
        type="tech_stack_detect",
        name="网页技术栈检测",
        description="通过 HTML 和 HTTP 响应头指纹识别目标网站使用的技术栈。",
        config_schema={"required": ["url"], "properties": {"url": "string"}},
    ),
    CollectorDefinition(
        type="spiderfoot_domain_osint",
        name="SpiderFoot 域名 OSINT",
        description="通过 SpiderFoot 对域名进行全面 OSINT 扫描。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="spiderfoot_ip_osint",
        name="SpiderFoot IP OSINT",
        description="通过 SpiderFoot 对 IP 地址进行 OSINT 扫描。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="spiderfoot_email_osint",
        name="SpiderFoot 邮箱 OSINT",
        description="通过 SpiderFoot 对邮箱地址进行 OSINT 扫描。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="spiderfoot_subdomain_enum",
        name="SpiderFoot 子域名枚举",
        description="通过 SpiderFoot 枚举目标域名的所有子域名。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="spiderfoot_threat_intel",
        name="SpiderFoot 威胁情报",
        description="通过 SpiderFoot 收集目标的威胁情报信息。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="spiderfoot_breach_check",
        name="SpiderFoot 数据泄露检测",
        description="通过 SpiderFoot 检测目标是否出现在已知数据泄露事件中。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="spiderfoot_cert_transparency",
        name="SpiderFoot 证书透明度",
        description="通过 SpiderFoot 查询证书透明度日志，发现相关域名和子域名。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="spiderfoot_dark_web",
        name="SpiderFoot 暗网监控",
        description="通过 SpiderFoot 在暗网来源中搜索目标相关信息。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="spiderfoot_attack_surface",
        name="SpiderFoot 攻击面分析",
        description="通过 SpiderFoot 全面分析目标的攻击面。",
        config_schema={
            "required": ["target"],
            "properties": {"target": "string", "modules": "array"},
        },
    ),
    CollectorDefinition(
        type="aliens_eye_basic",
        name="Aliens Eye 基础扫描",
        description="通过 ML 检测在 840+ 平台快速搜索用户名。",
        config_schema={"required": ["username"], "properties": {"username": "string"}},
    ),
    CollectorDefinition(
        type="aliens_eye_advanced",
        name="Aliens Eye 高级扫描",
        description="带用户名变体（前缀/后缀）的全量平台扫描，可指定平台范围。",
        config_schema={"required": ["username"], "properties": {"username": "string", "sites": "string"}},
    ),
    CollectorDefinition(
        type="aliens_eye_correlate",
        name="Aliens Eye 跨站关联",
        description="扫描后按头像哈希、Bio、共享链接聚类同一人的多个账号。",
        config_schema={"required": ["username"], "properties": {"username": "string"}},
    ),
    CollectorDefinition(
        type="aliens_eye_recurse",
        name="Aliens Eye 递归扩展",
        description="递归追踪 Bio 中发现的其他用户名并继续扫描。",
        config_schema={"required": ["username"], "properties": {"username": "string", "depth": "integer"}},
    ),
    CollectorDefinition(
        type="aliens_eye_domain",
        name="Aliens Eye 域名检测",
        description="检测 username.com/.io/.net 等常见域名变体是否已注册。",
        config_schema={"required": ["username"], "properties": {"username": "string"}},
    ),
    CollectorDefinition(
        type="aliens_eye_batch",
        name="Aliens Eye 批量扫描",
        description="一次扫描多个用户名（最多 10 个）。",
        config_schema={"required": ["usernames"], "properties": {"usernames": "array"}},
    ),
    CollectorDefinition(
        type="aliens_eye_selfcheck",
        name="Aliens Eye 准确率报告",
        description="运行内置自检，返回各平台检测精确率/召回率/F1 指标。",
        config_schema={"required": [], "properties": {}},
    ),
    CollectorDefinition(
        type="robin_darkweb_search",
        name="Robin 暗网关键词搜索",
        description="通过 Tor 在 8 个暗网搜索引擎搜索关键词，返回 .onion 结果。",
        config_schema={"required": ["keyword"], "properties": {"keyword": "string", "max_results": "integer"}},
    ),
    CollectorDefinition(
        type="robin_darkweb_username",
        name="Robin 暗网用户名搜索",
        description="在暗网搜索用户名相关的泄露信息和市场记录。",
        config_schema={"required": ["username"], "properties": {"username": "string", "max_results": "integer"}},
    ),
    CollectorDefinition(
        type="robin_darkweb_email",
        name="Robin 暗网邮箱泄露检测",
        description="在暗网搜索邮箱是否出现在泄露数据库或凭证列表中。",
        config_schema={"required": ["email"], "properties": {"email": "string", "max_results": "integer"}},
    ),
    CollectorDefinition(
        type="browser_use_task",
        name="Browser Use AI 任务采集",
        description="用自然语言描述采集任务，AI 控制浏览器自动完成采集。",
        config_schema={"required": ["task"], "properties": {"task": "string", "url": "string", "max_steps": "integer"}},
    ),
    CollectorDefinition(
        type="hackernews_front_page",
        name="Hacker News 首页热门",
        description="抓取 Hacker News 首页热门文章，免费无需 API Key。",
        config_schema={"required": [], "properties": {"max_items": "integer"}},
    ),
    CollectorDefinition(
        type="hackernews_search",
        name="Hacker News 搜索",
        description="通过 Algolia 搜索 Hacker News 历史帖子。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="hackernews_user",
        name="Hacker News 用户提交",
        description="抓取指定 HN 用户的提交记录。",
        config_schema={"required": ["username"], "properties": {"username": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="npm_package",
        name="npm 包信息",
        description="从 npm registry 获取包的详细元数据。",
        config_schema={"required": ["package"], "properties": {"package": "string"}},
    ),
    CollectorDefinition(
        type="npm_search",
        name="npm 包搜索",
        description="按关键词搜索 npm 包。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="pypi_package",
        name="PyPI 包信息",
        description="从 PyPI 获取 Python 包的详细元数据。",
        config_schema={"required": ["package"], "properties": {"package": "string"}},
    ),
    CollectorDefinition(
        type="pypi_search",
        name="PyPI 包搜索",
        description="通过 PyPI RSS 搜索 Python 包。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="crates_package",
        name="crates.io Rust 包信息",
        description="从 crates.io 获取 Rust 包的详细元数据，包括版本、下载量、依赖等。",
        config_schema={"required": ["package"], "properties": {"package": "string"}},
    ),
    CollectorDefinition(
        type="crates_search",
        name="crates.io Rust 包搜索",
        description="按关键词搜索 crates.io 上的 Rust 包。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="rubygems_package",
        name="RubyGems 包信息",
        description="从 RubyGems 获取 Ruby gem 的详细元数据，包括版本、依赖、下载量等。",
        config_schema={"required": ["package"], "properties": {"package": "string"}},
    ),
    CollectorDefinition(
        type="rubygems_search",
        name="RubyGems 包搜索",
        description="按关键词搜索 RubyGems 上的 Ruby gem。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="go_package",
        name="pkg.go.dev Go 包信息",
        description="从 pkg.go.dev 获取 Go 包的文档和元数据。package 为完整 import path（如 github.com/gin-gonic/gin）。",
        config_schema={"required": ["package"], "properties": {"package": "string"}},
    ),
    CollectorDefinition(
        type="go_search",
        name="pkg.go.dev Go 包搜索",
        description="在 pkg.go.dev 搜索 Go 包。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="packagist_package",
        name="Packagist PHP 包信息",
        description="从 Packagist 获取 PHP composer 包的详细元数据，包括版本、下载量、依赖等。package 格式为 vendor/name（如 laravel/framework）。",
        config_schema={"required": ["package"], "properties": {"package": "string"}},
    ),
    CollectorDefinition(
        type="packagist_search",
        name="Packagist PHP 包搜索",
        description="按关键词搜索 Packagist 上的 PHP composer 包。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="nuget_package",
        name="NuGet .NET 包信息",
        description="从 NuGet 获取 .NET 包的详细元数据，包括版本、下载量、作者等。",
        config_schema={"required": ["package"], "properties": {"package": "string"}},
    ),
    CollectorDefinition(
        type="nuget_search",
        name="NuGet .NET 包搜索",
        description="按关键词搜索 NuGet 上的 .NET 包。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="pubdev_package",
        name="pub.dev Dart/Flutter 包信息",
        description="从 pub.dev 获取 Dart/Flutter 包的详细元数据，包括版本、依赖等。",
        config_schema={"required": ["package"], "properties": {"package": "string"}},
    ),
    CollectorDefinition(
        type="pubdev_search",
        name="pub.dev Dart/Flutter 包搜索",
        description="按关键词搜索 pub.dev 上的 Dart/Flutter 包。",
        config_schema={"required": ["query"], "properties": {"query": "string", "max_items": "integer"}},
    ),
    CollectorDefinition(
        type="apify_1688_product_search",
        name="1688 商品搜索",
        description="按关键词搜索 1688.com 批发商品，返回价格梯度、MOQ、供应商信息。",
        config_schema={"required": ["keyword"], "properties": {"keyword": "string", "max_items_per_url": "integer"}},
    ),
    CollectorDefinition(
        type="apify_1688_product_detail",
        name="1688 商品详情",
        description="批量抓取 1688.com 商品详情页，返回 SKU、价格梯度、MOQ、供应商。",
        config_schema={"required": ["urls"], "properties": {"urls": "array"}},
    ),
    CollectorDefinition(
        type="apify_1688_advanced",
        name="1688 高级采集（含图片反查/到岸成本）",
        description="支持关键词搜索、以图搜货（图片 URL 反查）和到岸成本估算。",
        config_schema={"required": ["type", "queries"], "properties": {"type": "string", "queries": "array", "shippingCountry": "string"}},
    ),
    CollectorDefinition(
        type="apify_alibaba_product_search",
        name="阿里巴巴国际站商品搜索（含规格/证书）",
        description="采集 Alibaba.com 商品，支持规格书、CE/RoHS 认证信息、包装尺寸/重量。",
        config_schema={"required": ["startUrls"], "properties": {"startUrls": "array", "maxItems": "integer"}},
    ),
    CollectorDefinition(
        type="apify_alibaba_product_detail",
        name="阿里巴巴国际站商品详情（梯级报价）",
        description="抓取 Alibaba.com 单品详情，返回梯级报价、供应商资质、交货期。",
        config_schema={"required": ["productUrls"], "properties": {"productUrls": "array"}},
    ),
    CollectorDefinition(
        type="apify_amazon_bestsellers",
        name="Amazon BSR 最佳卖家榜",
        description="抓取 Amazon 分类 Best Sellers / New Releases 榜单，返回排名、价格、评分。",
        config_schema={"required": ["categoryUrls"], "properties": {"categoryUrls": "array", "maxResults": "integer"}},
    ),
    CollectorDefinition(
        type="apify_amazon_competitor_research",
        name="Amazon 竞品批量研究（BSR/FBA/卖家数）",
        description="按 ASIN 批量研究 Amazon 竞品，返回 BSR、FBA 状态、卖家数量，替代 Jungle Scout。",
        config_schema={"required": ["asins"], "properties": {"asins": "array", "marketplace": "string"}},
    ),
    CollectorDefinition(
        type="apify_amazon_bsr_tracker",
        name="Amazon BSR 时序追踪（多站点）",
        description="追踪指定 ASIN 在多 Amazon 站点的 BSR 变化，适合日度定时任务，替代 Keepa。",
        config_schema={"required": ["asins"], "properties": {"asins": "array", "marketplaces": "array"}},
    ),
    CollectorDefinition(
        type="apify_amazon_price_tracker",
        name="Amazon + Shopify 跨平台价格追踪",
        description="同时追踪 Amazon 和 Shopify 商品价格、库存、BSR 变化及 delta 告警。",
        config_schema={"required": ["products"], "properties": {"products": "array"}},
    ),
    CollectorDefinition(
        type="apify_aliexpress_product_search_v2",
        name="AliExpress 商品搜索（多货币/多国运费）",
        description="高质量 AliExpress 采集，支持 30+ 货币、40+ 收货国运费，适合 Dropshipping 利润估算。",
        config_schema={"required": ["queries"], "properties": {"queries": "array", "shipTo": "string", "currency": "string"}},
    ),
    CollectorDefinition(
        type="apify_shopify_products_monitor",
        name="Shopify 独立站实时价格/库存监控",
        description="实时监控 Shopify 独立站全品类价格和库存，适合竞品价格追踪。",
        config_schema={"required": ["url"], "properties": {"url": "string", "maxProducts": "integer"}},
    ),
    CollectorDefinition(
        type="apify_shopify_full_catalog",
        name="Shopify 独立站全品类 SKU 采集",
        description="通过 /products.json 高效采集 Shopify 独立站全品类商品和变体。",
        config_schema={"required": ["startUrls"], "properties": {"startUrls": "array", "maxProducts": "integer"}},
    ),
    CollectorDefinition(
        type="exa_search",
        name="Exa 神经语义搜索",
        description="Exa AI 语义搜索引擎，支持 auto/fast/instant/deep/deep-reasoning 模式及 company/people/publication/news 专项索引。",
        config_schema={"required": ["query"], "properties": {"query": "string", "search_type": "string", "category": "string", "num_results": "integer", "contents_mode": "string", "output_schema": "object"}},
    ),
    CollectorDefinition(
        type="exa_find_similar",
        name="Exa 相似 URL 发现",
        description="输入种子 URL，在向量空间中找语义最近邻页面，用于竞品发现和内容推荐。",
        config_schema={"required": ["url"], "properties": {"url": "string", "num_results": "integer", "exclude_source_domain": "boolean", "contents_mode": "string"}},
    ),
    CollectorDefinition(
        type="exa_contents",
        name="Exa URL 内容提取",
        description="输入已知 URL 列表，提取 highlights/text/summary 多模式结构化内容，支持子页面递归。",
        config_schema={"required": ["urls"], "properties": {"urls": "array", "contents_mode": "string", "max_age_hours": "integer", "subpages": "integer"}},
    ),
    CollectorDefinition(
        type="exa_answer",
        name="Exa 带引用问答",
        description="输入自然语言问题，返回综合答案 + 信源引用（标题/URL/日期/作者）。",
        config_schema={"required": ["query"], "properties": {"query": "string", "output_schema": "object", "text": "boolean"}},
    ),
    # 以下 4 个 collector 早已在 registry 注册并有校验函数，但此前遗漏在播种清单里，
    # 导致生产 quick-collect 一律返回 400 "Collector ... is not available"。
    CollectorDefinition(
        type="autoscraper_enhanced_web",
        name="AutoScraper 智能提取",
        description="给示例样本自动学习网页结构并批量提取同类字段，适合无固定模板的页面。",
        config_schema={
            "required": ["url", "wanted_list"],
            "properties": {"url": "string", "wanted_list": "array", "mode": "string", "save_rules": "boolean", "rules_path": "string"},
        },
    ),
    CollectorDefinition(
        type="bestblogs_articles",
        name="BestBlogs AI 精选文章",
        description="BestBlogs 平台聚合的 AI/技术精选文章、评分与摘要。",
        config_schema={"required": [], "properties": {"category": "string", "lang": "string", "min_score": "integer", "limit": "integer"}},
    ),
    CollectorDefinition(
        type="blackbird_email_osint",
        name="Blackbird 邮箱 OSINT",
        description="通过 Blackbird API 查询邮箱关联的公开账号画像。",
        config_schema={"required": ["email"], "properties": {"email": "string"}},
    ),
    CollectorDefinition(
        type="blackbird_username_osint",
        name="Blackbird 用户名 OSINT",
        description="通过 Blackbird API 查询用户名在公开平台的注册情况。",
        config_schema={"required": ["username"], "properties": {"username": "string"}},
    ),
)


async def ensure_collectors_seeded(session: AsyncSession) -> None:
    existing = {collector.type for collector in await list_collectors(session)}
    for definition in COLLECTOR_CATALOG:
        if definition.type not in existing:
            session.add(
                Collector(
                    type=definition.type,
                    name=definition.name,
                    description=definition.description,
                    config_schema=definition.config_schema,
                    enabled=True,
                )
            )
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        pass


async def require_collector(session: AsyncSession, collector_type: str) -> Collector:
    await ensure_collectors_seeded(session)
    collector = await get_collector_by_type(session, collector_type)
    if collector is None or not collector.enabled:
        from data_intelligence_hub.services.exceptions import CollectorNotFoundError

        raise CollectorNotFoundError
    return collector


def validate_collector_config(collector_type: str, config: dict[str, Any]) -> dict[str, Any]:
    if collector_type == "github_repo":
        return _validate_github_repo_config(config)
    if collector_type == "github_topic":
        return _validate_github_topic_config(config)
    if collector_type == "generic_web":
        return _validate_generic_web_config(config)
    if collector_type == "autoscraper_enhanced_web":
        return _validate_autoscraper_enhanced_web_config(config)
    if collector_type == "public_feed":
        return _validate_public_feed_config(config)
    if collector_type == "manual_json":
        return _validate_manual_json_config(config)
    if collector_type == "ecommerce_product_page":
        return _validate_ecommerce_product_page_config(config)
    if collector_type == "ecommerce_product_discovery":
        return _validate_ecommerce_product_discovery_config(config)

    if collector_type == "tikhub_social":
        return _validate_tikhub_social_config(config)
    if collector_type == "apify_actor":
        return _validate_apify_actor_config(config)
    if collector_type == "playwright_browser":
        return _validate_playwright_browser_config(config)
    if collector_type == "anysearch":
        return _validate_anysearch_config(config)
    if collector_type == "jina_reader":
        return _validate_jina_reader_config(config)
    if collector_type == "exa_search":
        return _validate_exa_search_config(config)
    if collector_type == "exa_find_similar":
        return _validate_exa_find_similar_config(config)
    if collector_type == "exa_contents":
        return _validate_exa_contents_config(config)
    if collector_type == "exa_answer":
        return _validate_exa_answer_config(config)

    if collector_type in {
        "sherlock", "maigret",
        "twscrape_search", "twscrape_user_tweets", "twscrape_trends",
        "anydoc_file_to_markdown",
        "bilibili_video_search", "bilibili_video_info", "bilibili_user_videos", "bilibili_video_comments",
        "weibo_keyword_search", "weibo_user_posts", "weibo_trending_topics",
        "zhihu_question_answers", "zhihu_keyword_search", "zhihu_hot_list",
        "baidu_search", "bing_search", "duckduckgo_search",
        "kuaishou_video_search", "kuaishou_user_videos",
        "firecrawl_crawl", "firecrawl_extract", "firecrawl_batch_scrape",
        "devto_articles", "juejin_articles", "substack_posts",
        "tech_stack_detect",
        "spiderfoot_domain_osint", "spiderfoot_ip_osint", "spiderfoot_email_osint",
        "spiderfoot_subdomain_enum", "spiderfoot_threat_intel", "spiderfoot_breach_check",
        "spiderfoot_cert_transparency", "spiderfoot_dark_web", "spiderfoot_attack_surface",
        "bestblogs_articles",
        "blackbird_email_osint", "blackbird_username_osint",
        "aliens_eye_basic", "aliens_eye_advanced", "aliens_eye_correlate",
        "aliens_eye_recurse", "aliens_eye_domain", "aliens_eye_batch",
        "aliens_eye_selfcheck",
        "robin_darkweb_search", "robin_darkweb_username", "robin_darkweb_email",
        "browser_use_task",
        "hackernews_front_page", "hackernews_search", "hackernews_user",
        "npm_package", "npm_search",
        "pypi_package", "pypi_search",
        "crates_package", "crates_search",
        "rubygems_package", "rubygems_search",
        "go_package", "go_search",
        "packagist_package", "packagist_search",
        "nuget_package", "nuget_search",
        "pubdev_package", "pubdev_search",
        "apify_1688_product_search", "apify_1688_product_detail", "apify_1688_advanced",
        "apify_alibaba_product_search", "apify_alibaba_product_detail",
        "apify_amazon_bestsellers", "apify_amazon_competitor_research",
        "apify_amazon_bsr_tracker", "apify_amazon_price_tracker",
        "apify_aliexpress_product_search_v2",
        "apify_shopify_products_monitor", "apify_shopify_full_catalog",
    }:
        return _validate_passthrough_config(config)

    from data_intelligence_hub.services.exceptions import CollectorNotFoundError

    raise CollectorNotFoundError


def _require_text(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or value.strip() == "":
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return value.strip()


def _validate_github_repo_config(config: dict[str, Any]) -> dict[str, Any]:
    url = config.get("url", "")
    if url and isinstance(url, str):
        parts = url.rstrip("/").split("/")
        if len(parts) >= 2:
            return {"owner": parts[-2], "repo": parts[-1]}
    return {"owner": _require_text(config, "owner"), "repo": _require_text(config, "repo")}


def _validate_github_topic_config(config: dict[str, Any]) -> dict[str, Any]:
    topic = _require_text(config, "topic")
    max_results = config.get("max_results", 30)
    if not isinstance(max_results, int) or max_results < 1 or max_results > 100:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"topic": topic, "max_results": max_results}


def _validate_generic_web_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _require_text(config, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    extract_mode = config.get("extract_mode", "main_content")
    if extract_mode not in {"full_html", "main_content"}:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"url": url, "extract_mode": extract_mode}


def _validate_autoscraper_enhanced_web_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _require_text(config, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    wanted_list = config.get("wanted_list", [])
    if not isinstance(wanted_list, list) or not wanted_list:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    mode = config.get("mode", "exact")
    if mode not in {"exact", "similar"}:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    save_rules = config.get("save_rules", False)
    rules_path = config.get("rules_path")
    return {
        "url": url,
        "wanted_list": wanted_list,
        "mode": mode,
        "save_rules": save_rules,
        "rules_path": rules_path,
    }


def _validate_public_feed_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _require_text(config, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    feed_type = config.get("feed_type", "auto")
    if feed_type not in {"auto", "rss", "atom"}:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    max_items = config.get("max_items", 20)
    if not isinstance(max_items, int) or max_items < 1 or max_items > 100:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"url": url, "feed_type": feed_type, "max_items": max_items}


def _validate_manual_json_config(config: dict[str, Any]) -> dict[str, Any]:
    entity_type = _require_text(config, "entity_type")
    json_data = config.get("json_data")
    if not isinstance(json_data, dict | list):
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"entity_type": entity_type, "json_data": json_data}


def _validate_ecommerce_product_page_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _require_text(config, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    fields = config.get(
        "fields",
        [
            "title",
            "price",
            "price_min",
            "price_max",
            "currency",
            "availability",
            "availability_detail",
            "sku",
            "variant",
            "brand",
            "category",
            "description",
            "image_url",
            "canonical_url",
        ],
    )
    allowed_fields = {
        "title",
        "price",
        "price_min",
        "price_max",
        "currency",
        "availability",
        "availability_detail",
        "sku",
        "variant",
        "brand",
        "category",
        "description",
        "image_url",
        "canonical_url",
    }
    if not isinstance(fields, list) or not fields:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    normalized_fields: list[str] = []
    for field in fields:
        if not isinstance(field, str) or field not in allowed_fields:
            from data_intelligence_hub.services.exceptions import CollectorConfigError

            raise CollectorConfigError
        normalized_fields.append(field)
    platform_hint = config.get("platform_hint", "auto")
    if platform_hint not in {"auto", "shopify", "independent_ecommerce"}:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"url": url, "fields": normalized_fields, "platform_hint": platform_hint}


def _validate_ecommerce_product_discovery_config(config: dict[str, Any]) -> dict[str, Any]:
    url = _require_text(config, "url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    max_products = config.get("max_products", 50)
    if not isinstance(max_products, int) or max_products < 1 or max_products > 200:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    platform_hint = config.get("platform_hint", "auto")
    if platform_hint not in {"auto", "shopify", "independent_ecommerce"}:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {"url": url, "max_products": max_products, "platform_hint": platform_hint}


_TIKHUB_ENDPOINT_TYPES = {
    "tikhub_tiktok_video_search",
    "tikhub_tiktok_user_posts",
    "tikhub_tiktok_hashtag_posts",
    "tikhub_instagram_search",
    "tikhub_instagram_user_posts",
    "tikhub_xiaohongshu_search",
    "tikhub_youtube_search",
    "tikhub_youtube_video_search",
    "tikhub_youtube_channel_videos",
    "tikhub_reddit_search",
    "tikhub_reddit_subreddit_posts",
    "tikhub_x_search",
    "tikhub_x_user_tweets",
    "tikhub_threads_search",
    "tikhub_threads_user_posts",
    "tikhub_threads_post_comments",
    "tikhub_linkedin_user_posts",
    "tikhub_linkedin_company_profile",
    "tikhub_linkedin_company_posts",
    "tikhub_linkedin_search_jobs",
    "tikhub_linkedin_job_detail",
    "tikhub_linkedin_post_comments",
    "tikhub_lemon8_search",
    "tikhub_lemon8_user_posts",
    "tikhub_lemon8_trending",
    "tikhub_tiktok_ads_search",
    "tikhub_tiktok_top_ads",
    "tikhub_tiktok_shop_products",
    "tikhub_tiktok_creator_info",
    "tikhub_instagram_post_comments",
    "tikhub_youtube_video_comments",
    "tikhub_reddit_post_comments",
    "tikhub_tiktok_live_search",
    "tikhub_tiktok_live_room_detail",
    "tikhub_tiktok_live_user",
    "tikhub_youtube_trending",
    "tikhub_reddit_trending",
    "tikhub_x_trending",
    "tikhub_tiktok_user_followers",
    "tikhub_instagram_user_followers",
    "tikhub_x_user_followers",
    "tikhub_tiktok_creator_insights",
    "tikhub_tiktok_creator_insights_trend",
    "tikhub_tiktok_creator_account_health",
    "tikhub_tiktok_ads_detail",
    "tikhub_tiktok_ads_keyword_suggest",
    "tikhub_douyin_video_search",
    "tikhub_douyin_user_posts",
    "tikhub_douyin_hot_search",
    "tikhub_douyin_comments",
    "tikhub_douyin_brand_hot_search",
    "tikhub_bilibili_video_search",
    "tikhub_bilibili_user_videos",
    "tikhub_bilibili_comments",
    "tikhub_weibo_search",
    "tikhub_weibo_user_posts",
    "tikhub_kuaishou_search",
    "tikhub_kuaishou_user_posts",
    "tikhub_wechat_search",
    "tikhub_wechat_channels_video",
    "tikhub_zhihu_search",
    "tikhub_zhihu_question_answers",
}


def _validate_tikhub_social_config(config: dict[str, Any]) -> dict[str, Any]:
    endpoint_type = _require_text(config, "endpoint_type")
    if endpoint_type not in _TIKHUB_ENDPOINT_TYPES:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    max_items = config.get("max_items", 20)
    if not isinstance(max_items, int) or not (1 <= max_items <= 100):
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    out: dict[str, Any] = {"endpoint_type": endpoint_type, "max_items": max_items}
    # 这份白名单必须覆盖 _build_params 里所有 config.get("X")：漏掉的键会被静默丢成 ""，
    # 上游于是报 400/422（2026-10-09 实测：subreddit 被丢 -> subreddit_name 长度不足）。
    for key in (
        "keyword", "unique_id", "ch_id", "user_id", "cursor", "max_cursor",
        "video_id", "url", "query", "sec_user_id", "screen_name", "urn",
        "room_id", "creator_uid", "query_id_str", "post_id", "shortcode",
        "code_or_url", "company_name", "company_username", "job_id",
        "uid", "bvid", "mid", "search_word", "ad_id", "ads_id",
        "username", "category_id",
        # _build_params 读取但此前不在白名单里的键
        "sort_type", "hashtag_id", "max_id", "pagination_token", "note_type",
        "page", "page_size", "order", "source", "channel_id", "subreddit",
        "aweme_id", "keywords", "post_urn", "offset", "question_id",
        "material_id", "industry", "country_code", "label", "tag",
        "since_id", "feature", "filter_type", "month", "search_type",
        "end_cursor", "pcursor",
    ):
        if key in config and config[key] is not None:
            out[key] = config[key]
    return out


def _validate_apify_actor_config(config: dict[str, Any]) -> dict[str, Any]:
    actor_id = _require_text(config, "actor_id")
    actor_input = config.get("actor_input")
    if not isinstance(actor_input, dict):
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    max_items = config.get("max_items", 20)
    if not isinstance(max_items, int) or not (1 <= max_items <= 1000):
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    max_charge = config.get("max_total_charge_usd", 1.0)
    if not isinstance(max_charge, (int, float)) or max_charge <= 0:
        from data_intelligence_hub.services.exceptions import CollectorConfigError

        raise CollectorConfigError
    return {
        "actor_id": actor_id,
        "actor_input": actor_input,
        "max_items": max_items,
        "max_total_charge_usd": float(max_charge),
    }


def _validate_playwright_browser_config(config: dict[str, Any]) -> dict[str, Any]:
    from data_intelligence_hub.services.exceptions import CollectorConfigError

    url = _require_text(config, "url")
    wait_for = config.get("wait_for", "load")
    if wait_for not in {"load", "networkidle", "domcontentloaded"}:
        raise CollectorConfigError
    extract_mode = config.get("extract_mode", "text")
    if extract_mode not in {"text", "html", "screenshot"}:
        raise CollectorConfigError
    return {"url": url, "wait_for": wait_for, "extract_mode": extract_mode}


def _validate_anysearch_config(config: dict[str, Any]) -> dict[str, Any]:
    from data_intelligence_hub.services.exceptions import CollectorConfigError

    query = _require_text(config, "query")
    num_results = config.get("num_results", 10)
    if not isinstance(num_results, int) or not (1 <= num_results <= 50):
        raise CollectorConfigError
    site = config.get("site")
    if site is not None and not isinstance(site, str):
        raise CollectorConfigError
    tag = config.get("tag")
    if tag is not None and not isinstance(tag, str):
        raise CollectorConfigError
    params = config.get("params")
    if params is not None and not isinstance(params, dict):
        raise CollectorConfigError
    return {"query": query, "num_results": num_results, "site": site, "tag": tag, "params": params}


def _validate_jina_reader_config(config: dict[str, Any]) -> dict[str, Any]:
    from data_intelligence_hub.services.exceptions import CollectorConfigError

    url = _require_text(config, "url")
    return_format = config.get("return_format", "markdown")
    if return_format not in {"markdown", "text", "html"}:
        raise CollectorConfigError
    return {"url": url, "return_format": return_format}


def _validate_exa_search_config(config: dict[str, Any]) -> dict[str, Any]:
    from data_intelligence_hub.services.exceptions import CollectorConfigError

    _VALID_SEARCH_TYPES = {
        "instant", "fast", "auto", "deep-lite", "deep", "deep-reasoning",
    }
    _DEEP_TYPES = {"deep-lite", "deep", "deep-reasoning"}
    _VALID_CATEGORIES = {
        "company", "people", "publication", "news",
        "personal site", "financial report",
    }
    _VALID_CONTENTS_MODES = {"highlights", "text", "summary", "none"}

    query = _require_text(config, "query")
    search_type = config.get("search_type", "auto")
    if search_type not in _VALID_SEARCH_TYPES:
        raise CollectorConfigError

    is_deep = search_type in _DEEP_TYPES
    max_n = 25 if is_deep else 10
    num_results = config.get("num_results", 10)
    if not isinstance(num_results, int) or not (1 <= num_results <= max_n):
        raise CollectorConfigError

    category = config.get("category")
    if category and category not in _VALID_CATEGORIES:
        raise CollectorConfigError

    contents_mode = config.get("contents_mode", "highlights")
    if contents_mode not in _VALID_CONTENTS_MODES:
        raise CollectorConfigError

    output_schema = config.get("output_schema")
    if output_schema is not None and not isinstance(output_schema, dict):
        raise CollectorConfigError

    include_domains = config.get("include_domains", [])
    exclude_domains = config.get("exclude_domains", [])
    if not isinstance(include_domains, list):
        raise CollectorConfigError
    if not isinstance(exclude_domains, list):
        raise CollectorConfigError

    return {
        "query": query,
        "search_type": search_type,
        "category": category,
        "num_results": num_results,
        "contents_mode": contents_mode,
        "output_schema": output_schema,
        "system_prompt": config.get("system_prompt"),
        "additional_queries": config.get("additional_queries"),
        "include_domains": include_domains,
        "exclude_domains": exclude_domains,
        "start_published_date": config.get("start_published_date"),
        "end_published_date": config.get("end_published_date"),
        "max_age_hours": config.get("max_age_hours"),
        "summary_query": config.get("summary_query"),
        "text_max_characters": config.get("text_max_characters"),
    }


def _validate_exa_find_similar_config(config: dict[str, Any]) -> dict[str, Any]:
    from data_intelligence_hub.services.exceptions import CollectorConfigError

    url = _require_text(config, "url")
    num_results = config.get("num_results", 10)
    if not isinstance(num_results, int) or not (1 <= num_results <= 25):
        raise CollectorConfigError
    exclude_source = config.get("exclude_source_domain", True)
    if not isinstance(exclude_source, bool):
        raise CollectorConfigError
    return {
        "url": url,
        "num_results": num_results,
        "exclude_source_domain": exclude_source,
        "contents_mode": config.get("contents_mode", "highlights"),
        "include_domains": config.get("include_domains", []),
        "exclude_domains": config.get("exclude_domains", []),
        "start_published_date": config.get("start_published_date"),
        "end_published_date": config.get("end_published_date"),
    }


def _validate_exa_contents_config(config: dict[str, Any]) -> dict[str, Any]:
    from data_intelligence_hub.services.exceptions import CollectorConfigError

    _VALID_CONTENTS_MODES = {"highlights", "text", "summary", "none"}

    urls = config.get("urls", [])
    if not isinstance(urls, list) or not urls:
        raise CollectorConfigError
    if len(urls) > 100:
        raise CollectorConfigError
    for u in urls:
        if not isinstance(u, str) or not u.strip():
            raise CollectorConfigError

    contents_mode = config.get("contents_mode", "highlights")
    if contents_mode not in _VALID_CONTENTS_MODES:
        raise CollectorConfigError

    subpages = config.get("subpages", 0)
    if not isinstance(subpages, int) or not (0 <= subpages <= 100):
        raise CollectorConfigError

    return {
        "urls": [u.strip() for u in urls],
        "contents_mode": contents_mode,
        "max_age_hours": config.get("max_age_hours"),
        "subpages": subpages,
        "subpage_target": config.get("subpage_target", []),
        "summary_query": config.get("summary_query"),
        "text_max_characters": config.get("text_max_characters"),
    }


def _validate_exa_answer_config(config: dict[str, Any]) -> dict[str, Any]:
    from data_intelligence_hub.services.exceptions import CollectorConfigError

    query = _require_text(config, "query")
    output_schema = config.get("output_schema")
    if output_schema is not None and not isinstance(output_schema, dict):
        raise CollectorConfigError
    return {
        "query": query,
        "output_schema": output_schema,
        "text": config.get("text", False),
    }


def _validate_passthrough_config(config: dict[str, Any]) -> dict[str, Any]:
    return dict(config)
