import type { DashboardSummary } from "@/types/dashboard";
import type { Entity, EntitySnapshot } from "@/types/entity";
import type { Evidence, IntelligenceItem } from "@/types/intelligence";
import type { AlertEvent, AlertRule } from "@/types/alert";
import type {
  AutomationProductDiscovery,
  AutomationDatasetExportFormat,
  AutomationProductBatchRun,
  AutomationProductBatchRunInput,
  AutomationProductDatasetPreview,
  AutomationProductDatasetPreviewInput,
  AutomationProductDatasetSave,
  AutomationProductDatasetExportCreateInput,
  AutomationProductDatasetExportJob,
  AutomationProductDatasetExportList,
  AutomationProductDatasetExportListInput,
  AutomationProductDatasetSaveInput,
  AutomationProductDatasetList,
  AutomationProductDatasetListInput,
  AutomationProductDatasetVersionList,
  AutomationProductDatasetVersionListInput,
  AutomationProductDriftCheck,
  AutomationProductDriftCheckInput,
  AutomationProductDriftAlertPreview,
  AutomationProductDriftAlertPreviewInput,
  AutomationProductDriftAlertEventCreate,
  AutomationProductDriftAlertEventCreateInput,
  AutomationProductDriftAlertNotificationSend,
  AutomationProductDriftAlertNotificationSendInput,
  AutomationProductDriftAlertEmailSend,
  AutomationProductDriftAlertEmailSendInput,
  AutomationProductDriftAlertRuleCreate,
  AutomationProductDriftAlertRuleCreateInput,
  AutomationProductDriftEvent,
  AutomationProductDriftEventList,
  AutomationProductDriftEventListInput,
  AutomationProductDriftEventSaveInput,
  AutomationProductFanoutCreate,
  AutomationProductFanoutCreateInput,
  AutomationProductFanoutPreview,
  AutomationProductFanoutPreviewInput,
  AutomationCapabilityProbeList,
  AutomationPlatformPackage,
  AutomationProductScheduleApprove,
  AutomationProductScheduleApproveInput,
  AutomationSiteAnalysis,
} from "@/types/automation";
import type {
  EmailChannelStatus,
  EmailChannelTestResult,
  NotificationItem,
} from "@/types/notification";
import type { AuthSession, Project } from "@/types/project";
import type { RawRecord } from "@/types/raw-record";
import type {
  Report,
  ReportAuditEvent,
  ReportDeliveryChannel,
  ReportEvidenceReference,
  ReportGenerateInput,
  ReportSubscription,
  ReportSubscriptionInput,
  ReportSubscriptionRun,
} from "@/types/report";
import type { Signal, SignalSnapshotCompare } from "@/types/signal";
import type {
  CollectionTask,
  Collector,
  SchedulerOverview,
  Source,
  TaskRun,
} from "@/types/source-task";

export function getMockAutomationPlatformPackages(): AutomationPlatformPackage[] {
  return [
    {
      id: "shopify-independent-ecommerce",
      name: "独立站 / Shopify-style 商品采集",
      category: "ecommerce",
      summary: "面向公开商品详情页和集合页，优先读取 Product JSON-LD、页面结构和同源商品链接。",
      supportedTargets: ["ecommerce_product", "ecommerce_product_collection"],
      collectorTypes: ["ecommerce_product_discovery", "ecommerce_product_page"],
      fieldSchema: [
        {
          key: "title",
          label: "商品标题",
          dataType: "string",
          required: true,
          source: "json_ld_or_dom",
          cleaningRule: "strip_text",
        },
        {
          key: "price",
          label: "价格",
          dataType: "decimal",
          required: false,
          source: "json_ld_or_dom",
          cleaningRule: "parse_decimal",
        },
        {
          key: "currency",
          label: "货币",
          dataType: "string",
          required: false,
          source: "json_ld_or_dom",
          cleaningRule: "uppercase",
        },
        {
          key: "availability",
          label: "库存状态",
          dataType: "enum",
          required: false,
          source: "json_ld_or_dom",
          cleaningRule: "normalize_availability",
        },
        {
          key: "sku",
          label: "SKU",
          dataType: "string",
          required: false,
          source: "json_ld_or_dom",
          cleaningRule: "fill_default",
        },
        {
          key: "canonical_url",
          label: "规范 URL",
          dataType: "url",
          required: true,
          source: "page_url_or_canonical",
          cleaningRule: "normalize_url",
        },
      ],
      defaultEntrypoint: "product-discovery",
      sampleUrls: [
        {
          label: "集合页样例",
          entrypoint: "product-discovery",
          url: "https://shop.example/collections/summer-bags",
          description: "从公开集合页发现商品 URL，再进入 fan-out 小批量采集。",
        },
        {
          label: "商品页样例",
          entrypoint: "site-analysis",
          url: "https://shop.example/products/demo-bag",
          description: "直接验证 Product JSON-LD、价格、SKU 和 canonical URL 字段。",
        },
      ],
      cleaningRules: [
        {
          field: "title",
          operation: "strip_text",
          description: "去除商品标题首尾空白并合并重复空格。",
        },
        {
          field: "price",
          operation: "parse_decimal",
          description: "将价格字段转换为可排序的 decimal number。",
        },
        {
          field: "currency",
          operation: "uppercase",
          description: "把货币代码统一为大写，便于跨站点合并。",
        },
        {
          field: "availability",
          operation: "normalize_availability",
          description: "库存状态归一为 in_stock/out_of_stock/unknown。",
        },
        {
          field: "sku",
          operation: "fill_default",
          value: "UNKNOWN-SKU",
          description: "缺失 SKU 时保留可审计默认值。",
        },
        {
          field: "canonical_url",
          operation: "normalize_url",
          description: "规范 URL 字段，降低重复商品记录。",
        },
      ],
      operatorChecklist: [
        "确认目标页面公开可访问，不依赖登录态、验证码或购物车状态。",
        "优先从集合页发现 5-20 个候选商品 URL，再人工剔除无关链接。",
        "保留 title、price、canonical_url 作为最小必选字段。",
        "先执行清洗计划试跑，确认价格和库存字段正常后再保存数据集版本。",
      ],
      strategyMatrix: [
        {
          id: "collection-to-products",
          label: "集合页发现商品 URL",
          entrypoint: "product-discovery",
          collectorType: "ecommerce_product_discovery",
          fit: "high",
          canStartFromAutomation: true,
          reviewRequired: true,
          description: "从公开集合页发现商品链接，人工确认后创建商品页任务。",
        },
        {
          id: "single-product-analysis",
          label: "单商品页字段解析",
          entrypoint: "site-analysis",
          collectorType: "ecommerce_product_page",
          fit: "high",
          canStartFromAutomation: true,
          reviewRequired: false,
          description: "解析一个公开商品详情页，生成字段候选和采集计划。",
        },
      ],
      riskBoundaries: [
        {
          condition: "页面公开访问且不需要登录态",
          severity: "info",
          guidance: "可在授权确认后进入小批量采集链路。",
        },
        {
          condition: "出现验证码、登录墙、购物车态或个人数据",
          severity: "blocked",
          guidance: "停止自动采集，改为人工评估或官方 API。",
        },
      ],
      sopLinks: [
        { label: "平台方法卡", href: "/toolkit?category=platform_method" },
        { label: "采集工作台", href: "/automation" },
      ],
      sampleFixture: {
        fixtureType: "deterministic_html",
        available: true,
        description: "E2E 使用固定商品页和集合页 fixture 验证。",
      },
      executionBoundary: "executable",
      runStarted: false,
    },
    {
      id: "github-api-first",
      name: "GitHub API-first 工具情报采集",
      category: "developer_platform",
      summary: "面向 GitHub topic、repo 和开源采集工具情报；优先使用官方 API。",
      supportedTargets: ["tool_repository", "topic_radar", "release_monitor"],
      collectorTypes: ["github_topic", "github_repo"],
      fieldSchema: [
        {
          key: "repo_full_name",
          label: "仓库全名",
          dataType: "string",
          required: true,
          source: "github_api",
          cleaningRule: "strip_text",
        },
        {
          key: "html_url",
          label: "仓库 URL",
          dataType: "url",
          required: true,
          source: "github_api",
          cleaningRule: "normalize_url",
        },
      ],
      defaultEntrypoint: "source-create",
      sampleUrls: [
        {
          label: "Topic 样例",
          entrypoint: "source-create",
          url: "https://github.com/topics/web-scraping",
          description: "从公开 topic 创建 GitHub API-first 采集源、任务并小批量运行。",
        },
      ],
      cleaningRules: [
        {
          field: "repo_full_name",
          operation: "strip_text",
          description: "去除仓库全名首尾空白。",
        },
        {
          field: "html_url",
          operation: "normalize_url",
          description: "规范仓库 URL。",
        },
      ],
      operatorChecklist: [
        "确认 GitHub API rate limit、token 权限和 topic 范围。",
        "优先使用官方 API，不解析登录态页面。",
        "将 stars、topics、html_url 作为工具情报排序和溯源字段。",
      ],
      strategyMatrix: [
        {
          id: "topic-radar-import",
          label: "Topic 工具雷达导入",
          entrypoint: "source-create",
          collectorType: "github_topic",
          fit: "high",
          canStartFromAutomation: true,
          reviewRequired: true,
          description: "从 Automation 创建 GitHub topic 采集源、启用任务，并执行一次小批量 API 采集。",
        },
      ],
      riskBoundaries: [
        {
          condition: "未配置 GitHub token 时使用公开 API 低频采集",
          severity: "warning",
          guidance: "限制 max_results 和手动运行次数；触发 rate limit 后不要自动重试放大请求。",
        },
      ],
      sopLinks: [
        {
          label: "GitHub/API-first SOP",
          href: "/toolkit?category=platform_method&platform=github",
        },
        { label: "采集源配置", href: "/sources" },
      ],
      sampleFixture: {
        fixtureType: "api_fixture",
        available: true,
        description: "单元测试覆盖 GitHub collector 配置校验和 API 响应解析。",
      },
      executionBoundary: "executable",
      runStarted: false,
    },
    {
      id: "public-page-structure-preflight",
      name: "公开网页结构解析预检",
      category: "browser_preflight",
      summary: "面向任意公开网页的采集前置诊断；先检查授权、robots、DOM 摘要和链接结构。",
      supportedTargets: ["public_web_page", "site_structure", "field_contract_draft"],
      collectorTypes: ["toolkit_preflight", "generic_web"],
      fieldSchema: [
        {
          key: "page_title",
          label: "页面标题",
          dataType: "string",
          required: true,
          source: "html_title",
          cleaningRule: "strip_text",
        },
        {
          key: "canonical_url",
          label: "规范 URL",
          dataType: "url",
          required: true,
          source: "canonical_or_final_url",
          cleaningRule: "normalize_url",
        },
        {
          key: "meta_description",
          label: "页面描述",
          dataType: "string",
          required: false,
          source: "meta_description",
          cleaningRule: "strip_text",
        },
        {
          key: "headings",
          label: "标题层级",
          dataType: "string_array",
          required: false,
          source: "dom_h1_h2_h3",
          cleaningRule: "strip_text",
        },
        {
          key: "same_origin_links",
          label: "同源链接",
          dataType: "integer",
          required: false,
          source: "dom_links",
          cleaningRule: "fill_default",
        },
        {
          key: "text_sample",
          label: "正文样本",
          dataType: "text",
          required: false,
          source: "visible_text",
          cleaningRule: "strip_text",
        },
      ],
      defaultEntrypoint: "preflight",
      sampleUrls: [
        {
          label: "公开网页样例",
          entrypoint: "preflight",
          url: "https://example.com",
          description: "生成采集前置预检报告，确认 URL、robots、DOM、链接结构和工具选择。",
        },
      ],
      cleaningRules: [
        {
          field: "page_title",
          operation: "strip_text",
          description: "去除页面标题首尾空白并合并重复空格。",
        },
        {
          field: "canonical_url",
          operation: "normalize_url",
          description: "规范最终 URL 和 canonical URL。",
        },
        {
          field: "text_sample",
          operation: "strip_text",
          description: "压缩正文样本文本空白。",
        },
      ],
      operatorChecklist: [
        "确认目标 URL 属于自有、授权或明确允许分析的公开页面。",
        "先看 robots、sitemap、security.txt 和表单数量，再决定是否继续。",
        "把 title、canonical_url、headings、text_sample 作为首轮字段契约。",
        "脚本多或关键内容不可见时，再升级到浏览器方案。",
      ],
      strategyMatrix: [
        {
          id: "public-url-structure-preflight",
          label: "公开 URL 结构预检",
          entrypoint: "preflight",
          collectorType: "toolkit_preflight",
          fit: "high",
          canStartFromAutomation: true,
          reviewRequired: true,
          description: "调用预检 API，输出授权 gate、DOM 摘要、资源线索和后续工具建议。",
        },
        {
          id: "preflight-to-generic-web",
          label: "预检后创建 generic_web 采集源",
          entrypoint: "source-create",
          collectorType: "generic_web",
          fit: "medium",
          canStartFromAutomation: true,
          reviewRequired: true,
          description: "预检未触发阻断项后，将最终 URL 创建为 generic_web 采集源。",
        },
      ],
      riskBoundaries: [
        {
          condition: "公开页面、robots 未给出全站禁止信号，且不依赖账号态",
          severity: "info",
          guidance: "可在授权确认后生成预检报告，并小批量验证 generic_web 采集。",
        },
        {
          condition: "出现登录墙、验证码、私网地址、账号参数或个人数据",
          severity: "blocked",
          guidance: "停止自动化采集，转入人工授权或官方 API 路线。",
        },
      ],
      sopLinks: [
        { label: "授权 URL 预检向导", href: "/toolkit?category=governance" },
        { label: "浏览器解析实验室", href: "/toolkit?category=browser_automation" },
      ],
      sampleFixture: {
        fixtureType: "http_preflight_fixture",
        available: true,
        description: "单元测试使用固定 HTML、robots 和 sitemap 响应验证预检报告。",
      },
      executionBoundary: "executable",
      runStarted: false,
    },
  ];
}

export function getMockDashboard(domain?: string): DashboardSummary {
  const allTop = getMockIntelligence().map((item) => ({
    id: item.id,
    title: item.title,
    summary: item.summary,
    domain: item.domain,
    type: item.intelligenceType,
    evidenceCount: item.evidenceCount,
    finalScore: item.finalScore,
    status: item.status,
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
  }));
  const topIntelligence = domain ? allTop.filter((item) => item.domain === domain) : allTop;
  const typeCounts = topIntelligence.reduce<Record<string, number>>((accumulator, item) => {
    accumulator[item.type] = (accumulator[item.type] ?? 0) + 1;
    return accumulator;
  }, {});
  const projectCount = getMockProjects().filter((project) => !domain || project.domain === domain).length;
  const sourceCount = getMockSources().filter((source) => {
    const project = getMockProjects().find((item) => item.id === source.projectId);
    return !domain || project?.domain === domain;
  }).length;
  return {
    intelligenceCount: topIntelligence.length,
    taskSuccessRate: topIntelligence.length > 0 ? 100 : 0,
    fieldCompleteness: topIntelligence.length > 0 ? 100 : 0,
    activeAlerts: 0,
    failedTasks: 0,
    recentRuns: topIntelligence.length > 0 ? 2 : 0,
    sourceCount,
    typeBreakdown: Object.entries(typeCounts).map(([type, count]) => ({
      type,
      count,
      percent: topIntelligence.length > 0 ? (count / topIntelligence.length) * 100 : 0,
    })),
    domainBreakdown: (domain ? [domain] : ["osint", "competitor"]).map((item) => ({
      domain: item,
      intelligenceCount: allTop.filter((entry) => entry.domain === item).length,
      signalCount: getMockSignals().filter((signal) => {
        const project = getMockProjects().find((projectItem) => projectItem.id === signal.projectId);
        return project?.domain === item;
      }).length,
      projectCount: getMockProjects().filter((project) => project.domain === item).length,
    })),
    topIntelligence,
    taskHealth: {
      totalTasks: projectCount > 0 ? 1 : 0,
      enabledTasks: projectCount > 0 ? 1 : 0,
      failedTasks: 0,
      recentRuns: topIntelligence.length > 0 ? 2 : 0,
      recentFailures: [],
    },
    freshness: {
      generatedAt: new Date().toISOString(),
      latestCollectionAt: "2026-06-11T16:25:02.000Z",
      staleEnabledTasks: 0,
      staleTasks: [],
    },
  };
}

export function getMockAuthSession(email: string, name = "Demo User"): AuthSession {
  return {
    user: {
      id: "user_mock",
      email,
      name,
      status: "active",
    },
    workspace: {
      id: "workspace_mock",
      name: `${name}'s Workspace`,
      slug: "demo-workspace",
      ownerId: "user_mock",
    },
  };
}

export function getMockProjects(): Project[] {
  return [
    {
      id: "project_osint",
      name: "AI Scrapy Tools",
      description: "Track GitHub projects in web scraping and data extraction.",
      domain: "osint",
      status: "active",
      intelligenceCount: 9,
      sourceCount: 3,
    },
    {
      id: "project_competitor",
      name: "Competitor Landing Pages",
      description: "Monitor product page and pricing changes on competitor sites.",
      domain: "competitor",
      status: "active",
      intelligenceCount: 4,
      sourceCount: 2,
    },
    {
      id: "project_marketplace_price",
      name: "Marketplace Price Radar",
      description: "Watch marketplace listings, price movement, and seller positioning.",
      domain: "ecommerce",
      status: "active",
      intelligenceCount: 2,
      sourceCount: 1,
    },
    {
      id: "project_social_launch",
      name: "Social Launch Signals",
      description: "Collect campaign posts and imported social mentions for launch tracking.",
      domain: "social",
      status: "archived",
      intelligenceCount: 1,
      sourceCount: 1,
    },
    {
      id: "project_growth_mix",
      name: "Growth Opportunity Mix",
      description: "Blend competitor, repository, and manual JSON signals for weekly review.",
      domain: "mixed",
      status: "active",
      intelligenceCount: 3,
      sourceCount: 0,
    },
  ];
}

export function getMockCollectors(): Collector[] {
  return [
    {
      id: "collector_ecommerce_product_discovery",
      type: "ecommerce_product_discovery",
      name: "Ecommerce Product Discovery",
      description: "Discover product URLs from a public collection, listing, or sitemap page.",
      configSchema: { required: ["url"], optional: ["max_products", "platform_hint"] },
      enabled: true,
    },
    {
      id: "collector_ecommerce_product_page",
      type: "ecommerce_product_page",
      name: "Ecommerce Product Page",
      description: "Analyze a public product page and extract structured product fields.",
      configSchema: { required: ["url"], optional: ["fields", "platform_hint"] },
      enabled: true,
    },
    {
      id: "collector_github_repo",
      type: "github_repo",
      name: "GitHub Repo",
      description: "Monitor a public GitHub repository.",
      configSchema: { required: ["owner", "repo"] },
      enabled: true,
    },
    {
      id: "collector_github_topic",
      type: "github_topic",
      name: "GitHub Topic",
      description: "Discover repositories by topic.",
      configSchema: { required: ["topic"] },
      enabled: true,
    },
    {
      id: "collector_generic_web",
      type: "generic_web",
      name: "Generic Web Page",
      description: "Monitor a single public page.",
      configSchema: { required: ["url"] },
      enabled: true,
    },
    {
      id: "collector_manual_json",
      type: "manual_json",
      name: "Manual JSON",
      description: "Import structured JSON manually.",
      configSchema: { required: ["entity_type", "json_data"] },
      enabled: true,
    },
  ];
}

export function getMockSources(): Source[] {
  return [
    {
      id: "source_shopify_collection_discovery",
      projectId: "project_marketplace_price",
      name: "Shopify 集合页商品发现",
      type: "ecommerce_product_discovery",
      url: "https://shop.example/collections/summer-bags",
      config: {
        url: "https://shop.example/collections/summer-bags",
        max_products: 50,
        platform_hint: "shopify",
      },
      scheduleCron: "0 7 * * *",
      enabled: true,
    },
    {
      id: "source_shopify_product_demo",
      projectId: "project_marketplace_price",
      name: "Shopify 商品页字段采集",
      type: "ecommerce_product_page",
      url: "https://shop.example/products/demo-bag",
      config: {
        url: "https://shop.example/products/demo-bag",
        fields: ["title", "price", "currency", "availability", "sku", "brand", "canonical_url"],
        platform_hint: "shopify",
      },
      scheduleCron: "0 8 * * *",
      enabled: true,
    },
    {
      id: "source_codex_repo",
      projectId: "project_osint",
      name: "OpenAI Codex Repository",
      type: "github_repo",
      url: null,
      config: {
        owner: "openai",
        repo: "codex",
      },
      scheduleCron: "0 */1 * * *",
      enabled: true,
    },
    {
      id: "source_scraping_topic",
      projectId: "project_osint",
      name: "Web Scraping Topic Radar",
      type: "github_topic",
      url: null,
      config: {
        topic: "web-scraping",
        max_results: 30,
      },
      scheduleCron: "0 8 * * *",
      enabled: true,
    },
    {
      id: "source_competitor_homepage",
      projectId: "project_competitor",
      name: "Competitor Homepage Watch",
      type: "generic_web",
      url: "https://example.com/product",
      config: {
        url: "https://example.com/product",
        extract_mode: "main_content",
      },
      scheduleCron: "*/30 * * * *",
      enabled: false,
    },
    {
      id: "source_manual_json",
      projectId: "project_osint",
      name: "Manual Product JSON",
      type: "manual_json",
      url: null,
      config: {
        entity_type: "product",
        json_data: { name: "Demo Product", price: 99 },
      },
      scheduleCron: "0 8 * * *",
      enabled: true,
    },
  ];
}

export function getMockTasks(): CollectionTask[] {
  const tasks: Array<MockTaskSeed> = [
    {
      id: "task_shopify_collection_discovery",
      projectId: "project_marketplace_price",
      sourceId: "source_shopify_collection_discovery",
      collectorType: "ecommerce_product_discovery",
      name: "Shopify 集合页商品发现",
      scheduleCron: "0 7 * * *",
      status: "enabled",
      successCount: 18,
      failureCount: 0,
      lastRunAt: "2026-06-11T16:20:18.000Z",
      projectName: "Marketplace Price Radar",
      projectDomain: "ecommerce",
      sourceName: "Shopify 集合页商品发现",
      sourceUrl: "https://shop.example/collections/summer-bags",
    },
    {
      id: "task_shopify_product_demo",
      projectId: "project_marketplace_price",
      sourceId: "source_shopify_product_demo",
      collectorType: "ecommerce_product_page",
      name: "Shopify 商品页字段采集",
      scheduleCron: "0 8 * * *",
      status: "enabled",
      successCount: 31,
      failureCount: 0,
      lastRunAt: "2026-06-11T16:26:18.000Z",
      projectName: "Marketplace Price Radar",
      projectDomain: "ecommerce",
      sourceName: "Shopify 商品页字段采集",
      sourceUrl: "https://shop.example/products/demo-bag",
    },
    {
      id: "task_twitter_keywords",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "manual_json",
      name: "Twitter 关键词流",
      scheduleCron: "*/5 * * * *",
      status: "enabled",
      successCount: 142,
      failureCount: 0,
      lastRunAt: "2026-06-11T16:25:02.000Z",
    },
    {
      id: "task_reddit_hot_posts",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "manual_json",
      name: "Reddit 热门帖",
      scheduleCron: "*/10 * * * *",
      status: "enabled",
      successCount: 119,
      failureCount: 6,
      lastRunAt: "2026-06-11T16:20:11.000Z",
    },
    {
      id: "task_amazon_best_sellers",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "manual_json",
      name: "Amazon Best Sellers",
      scheduleCron: "*/30 * * * *",
      status: "enabled",
      successCount: 189,
      failureCount: 2,
      lastRunAt: "2026-06-11T16:00:33.000Z",
    },
    {
      id: "task_amazon_review_scrape",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "generic_web",
      name: "Amazon Review 抓取",
      scheduleCron: "*/30 * * * *",
      status: "enabled",
      successCount: 176,
      failureCount: 10,
      lastRunAt: "2026-06-11T15:59:58.000Z",
    },
    {
      id: "task_google_trends",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "generic_web",
      name: "Google Trends 指数",
      scheduleCron: "0 * * * *",
      status: "enabled",
      successCount: 96,
      failureCount: 0,
      lastRunAt: "2026-06-11T16:00:05.000Z",
    },
    {
      id: "task_news_site_aggregate",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "generic_web",
      name: "新闻站点聚合",
      scheduleCron: "*/15 * * * *",
      status: "enabled",
      successCount: 105,
      failureCount: 3,
      lastRunAt: "2026-06-11T16:21:17.000Z",
    },
    {
      id: "task_brand_site_watch",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "generic_web",
      name: "品牌官网监测",
      scheduleCron: "*/30 * * * *",
      status: "enabled",
      successCount: 121,
      failureCount: 8,
      lastRunAt: "2026-06-11T16:10:42.000Z",
    },
    {
      id: "task_google_play_rank",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "manual_json",
      name: "Google Play 榜单",
      scheduleCron: "0 * * * *",
      status: "paused",
      successCount: 88,
      failureCount: 4,
      lastRunAt: "2026-06-11T15:00:29.000Z",
    },
    {
      id: "task_linkedin_company",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "manual_json",
      name: "LinkedIn 公司动态",
      scheduleCron: "*/15 * * * *",
      status: "enabled",
      successCount: 73,
      failureCount: 12,
      lastRunAt: "2026-06-11T16:15:03.000Z",
    },
    {
      id: "task_tiktok_topic",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "manual_json",
      name: "TikTok 话题榜",
      scheduleCron: "*/10 * * * *",
      status: "disabled",
      successCount: 81,
      failureCount: 10,
      lastRunAt: "2026-06-11T16:12:08.000Z",
    },
  ];
  return tasks.map(withMockTaskFreshness);
}

export function getMockSchedulerOverview(): SchedulerOverview {
  const finishedAt = new Date().toISOString();
  return {
    enabled: true,
    latestTick: {
      id: "scheduler_tick_mock_latest",
      leaseName: "collection_scheduler_tick",
      ownerId: "mock-scheduler",
      status: "completed",
      lockAcquired: true,
      startedAt: new Date(Date.now() - 950).toISOString(),
      finishedAt,
      scanned: 10,
      due: 2,
      started: 2,
      skippedRunning: 0,
      skippedInvalidSchedule: 0,
      taskErrors: 0,
      reportSubscriptionsScanned: 1,
      reportSubscriptionsDue: 0,
      reportSubscriptionsStarted: 0,
      reportSubscriptionsSkippedRunning: 0,
      reportSubscriptionErrors: 0,
      errorMessage: null,
    },
  };
}

type MockTaskSeed = Omit<
  CollectionTask,
  | "freshnessStatus"
  | "freshnessTargetHours"
  | "nextRunAt"
  | "retryAfterAt"
  | "retryDelayMinutes"
  | "schedulePolicy"
  | "staleHours"
>;

function withMockTaskFreshness(task: MockTaskSeed): CollectionTask {
  const freshnessStatus =
    task.status === "paused" || task.status === "disabled"
      ? task.status
      : task.failureCount >= 10
        ? "failed"
        : "fresh";
  const retryAfterAt =
    freshnessStatus === "failed" && task.lastRunAt
      ? new Date(new Date(task.lastRunAt).getTime() + 15 * 60_000).toISOString()
      : null;
  const nextRunAt =
    task.status === "paused" || task.status === "disabled"
      ? null
      : retryAfterAt ?? mockNextRunAt(task.lastRunAt, 24);
  return {
    ...task,
    projectName: task.projectName ?? "AI Scrapy Tools",
    projectDomain: task.projectDomain ?? "osint",
    sourceName: task.sourceName ?? task.name,
    sourceUrl: task.sourceUrl ?? null,
    schedulePolicy: task.scheduleCron ? "manual_refresh_only" : "auto_freshness",
    freshnessTargetHours: 24,
    freshnessStatus,
    nextRunAt,
    retryAfterAt,
    retryDelayMinutes: 15,
    staleHours: 0,
    latestRunStatus: freshnessStatus === "failed" ? "failed" : "success",
    latestRunErrorMessage:
      freshnessStatus === "failed" ? "Mock task reached failure threshold." : null,
    latestRunRecordsCount: Math.max(task.successCount, 0),
    latestRunEntitiesCount: Math.max(Math.round(task.successCount / 10), 0),
    latestRunStartedAt: task.lastRunAt,
    latestRunFinishedAt: task.lastRunAt,
    latestRunCreatedAt: task.lastRunAt,
  };
}

export function getMockAutomationCapabilityProbes(): AutomationCapabilityProbeList {
  const generatedAt = new Date().toISOString();
  const agentReach = {
    schemaVersion: "agent_reach_channel_probe.v1" as const,
    installed: false,
    commandPath: null,
    doctorStatus: "missing_tool" as const,
    activeBackend: null,
    requiresLogin: false,
    requiresProxy: false,
    blockedReason: "agent_reach_not_installed",
    platforms: [],
    readInvoked: false,
    searchInvoked: false,
    rawSummary: { side_effects: "no_read_no_search_no_write" },
  };
  return {
    schemaVersion: "capability_probe_list.v1",
    generatedAt,
    runStarted: false,
    collectionResourcesWritten: false,
    total: 3,
    items: [
      {
        schemaVersion: "capability_probe.v1",
        platformId: "github",
        platformLabel: "GitHub API-first",
        generatedAt,
        doctorStatus: "available",
        credentialMode: "token",
        executionBoundary: "executable",
        riskLevel: "low",
        backendCandidates: [
          {
            backendId: "official_github_api",
            label: "GitHub REST/Search API",
            priority: 1,
            status: "available",
            credentialMode: "token",
            requiresLogin: false,
            requiresProxy: false,
            evidenceLevel: "L1-repo-or-runtime",
            notes: ["正式事实源仍然是 GitHub 官方 API。"],
          },
          {
            backendId: "agent_reach_channel",
            label: "Agent Reach channel probe",
            priority: 2,
            status: "missing_tool",
            credentialMode: "unknown",
            requiresLogin: false,
            requiresProxy: false,
            evidenceLevel: "L1-repo-or-runtime",
            notes: ["Mock 状态下不调用 read/search。"],
          },
        ],
        agentReach,
        allowedOutputs: ["Source", "TaskRun", "RawRecord", "DatasetVersion", "Report"],
        forbiddenActions: ["login_bypass", "cookie_export", "notification_send"],
        nextActions: ["继续深化 GitHub release、README、license 和 issue activity 字段。"],
        runStarted: false,
        collectionResourcesWritten: false,
      },
      {
        schemaVersion: "capability_probe.v1",
        platformId: "browser_preflight",
        platformLabel: "Browser Harness read-only evidence",
        generatedAt,
        doctorStatus: "missing_tool",
        credentialMode: "browser_profile",
        executionBoundary: "read_only_probe",
        riskLevel: "medium",
        backendCandidates: [
          {
            backendId: "browser_harness_probe",
            label: "browser-harness CLI",
            priority: 1,
            status: "missing_tool",
            credentialMode: "browser_profile",
            requiresLogin: false,
            requiresProxy: false,
            evidenceLevel: "L1-repo-or-runtime",
            notes: ["只作为 selector/network/page evidence，不直接创建 Dataset。"],
          },
        ],
        agentReach: null,
        allowedOutputs: ["BrowserDiagnosticJobRun"],
        forbiddenActions: ["login_bypass", "cookie_export", "anti_detect"],
        nextActions: ["扩展 selector 求值和 network metadata。"],
        runStarted: false,
        collectionResourcesWritten: false,
      },
      {
        schemaVersion: "capability_probe.v1",
        platformId: "social_sop_import_only",
        platformLabel: "Twitter/X, Xiaohongshu, Instagram, LinkedIn",
        generatedAt,
        doctorStatus: "blocked",
        credentialMode: "manual_export",
        executionBoundary: "sop_only",
        riskLevel: "high",
        backendCandidates: [
          {
            backendId: "manual_sop_import",
            label: "Reviewed SOP/import template",
            priority: 1,
            status: "manual_review",
            credentialMode: "manual_export",
            requiresLogin: true,
            requiresProxy: false,
            evidenceLevel: "L1-repo-or-runtime",
            notes: ["默认只做 SOP/import-only。"],
          },
        ],
        agentReach,
        allowedOutputs: ["ExternalToolSnapshot"],
        forbiddenActions: ["cookie_export", "bulk_scroll_collection", "personal_profile_enrichment"],
        nextActions: ["保持自动采集禁用，只做字段模板和人工导入 SOP。"],
        runStarted: false,
        collectionResourcesWritten: false,
      },
    ],
  };
}

export function getMockAutomationSiteAnalysis(url: string): AutomationSiteAnalysis {
  const requestedUrl = url.trim() || "https://shop.example/products/demo-bag";
  const analyzedAt = new Date().toISOString();
  const sourceDraft = {
    type: "ecommerce_product_page",
    config: {
      url: requestedUrl,
      fields: ["title", "price", "currency", "availability", "sku", "brand", "canonical_url"],
      platform_hint: "shopify",
    },
    suggestedName: "商品页采集：Demo Carry Bag",
    scheduleCron: null,
  };
  const extractionPlan = {
    id: "mock-extraction-plan-1",
    siteAnalysisId: "mock-site-analysis-1",
    projectId: "mock-project-1",
    name: sourceDraft.suggestedName,
    versionNumber: 1,
    collectorType: sourceDraft.type,
    selectedFields: ["title", "price", "currency", "availability", "sku", "brand", "canonical_url"],
    sourceDraft,
    scheduleCron: sourceDraft.scheduleCron,
    status: "draft",
    riskLevel: "low",
    auditEvents: [{ event: "mock_plan_created", at: analyzedAt }],
    createdAt: analyzedAt,
    runStarted: false,
  };
  return {
    requestedUrl,
    analyzedAt,
    authorizationConfirmed: true,
    platformProfile: {
      platformType: requestedUrl.includes("myshopify") || requestedUrl.includes("shop")
        ? "shopify"
        : "independent_ecommerce",
      confidence: 0.89,
      indicators: ["schema.org Product JSON-LD", "product price meta", "Shopify theme runtime marker"],
      riskLevel: "low",
    },
    pageStructure: {
      pageType: "product_detail",
      title: "Demo Carry Bag",
      canonicalUrl: requestedUrl,
      scriptCount: 8,
      formCount: 1,
      imageCount: 6,
      productSchemaCount: 1,
      sameOriginLinkCount: 18,
      textSample:
        "Demo Carry Bag is a compact product fixture with price, SKU, stock status and canonical product URL.",
    },
    fieldCandidates: [
      {
        key: "title",
        label: "商品标题",
        value: "Demo Carry Bag",
        dataType: "string",
        source: "json_ld_or_meta",
        confidence: 0.92,
        selected: true,
        cleaningRule: "strip_text",
      },
      {
        key: "price",
        label: "价格",
        value: 129.9,
        dataType: "number",
        source: "json_ld_or_meta",
        confidence: 0.92,
        selected: true,
        cleaningRule: "parse_decimal",
      },
      {
        key: "currency",
        label: "货币",
        value: "USD",
        dataType: "string",
        source: "json_ld_or_meta",
        confidence: 0.78,
        selected: true,
        cleaningRule: "strip_text",
      },
      {
        key: "availability",
        label: "库存状态",
        value: "in_stock",
        dataType: "string",
        source: "json_ld_or_meta",
        confidence: 0.78,
        selected: true,
        cleaningRule: "normalize_enum",
      },
      {
        key: "sku",
        label: "SKU",
        value: "BAG-001",
        dataType: "string",
        source: "json_ld_or_meta",
        confidence: 0.78,
        selected: true,
        cleaningRule: "strip_text",
      },
      {
        key: "brand",
        label: "品牌",
        value: "Demo Brand",
        dataType: "string",
        source: "json_ld_or_meta",
        confidence: 0.78,
        selected: true,
        cleaningRule: "strip_text",
      },
      {
        key: "description",
        label: "描述",
        value: "A compact product fixture.",
        dataType: "string",
        source: "json_ld_or_meta",
        confidence: 0.78,
        selected: true,
        cleaningRule: "strip_text",
      },
      {
        key: "image_url",
        label: "主图",
        value: "https://shop.example/cdn/demo.jpg",
        dataType: "url",
        source: "json_ld_or_meta",
        confidence: 0.78,
        selected: true,
        cleaningRule: "normalize_url",
      },
      {
        key: "canonical_url",
        label: "规范 URL",
        value: requestedUrl,
        dataType: "url",
        source: "json_ld_or_meta",
        confidence: 0.92,
        selected: true,
        cleaningRule: "normalize_url",
      },
    ],
    toolRecommendations: [
      {
        tool: "ecommerce_product_page",
        collectorType: "ecommerce_product_page",
        fit: "primary",
        riskLevel: "low",
        reason: "商品结构字段已从 JSON-LD 或 meta 中识别，可直接进入结构化采集。",
      },
      {
        tool: "Generic Web",
        collectorType: "generic_web",
        fit: "evidence",
        riskLevel: "low",
        reason: "保留页面快照用于证据追溯和字段漂移对比。",
      },
    ],
    cleaningPlan: [
      { field: "title", operation: "strip_text", description: "去除首尾空白，保留原始语义。" },
      { field: "price", operation: "parse_decimal", description: "去除货币符号和千分位，保存为 decimal number。" },
      { field: "availability", operation: "normalize_enum", description: "归一化为 in_stock、out_of_stock 或 unknown。" },
      { field: "canonical_url", operation: "normalize_url", description: "转为绝对 URL，用于去重和回溯。" },
    ],
    sourceDraft,
    blockedReasons: [],
    siteAnalysis: {
      id: "mock-site-analysis-1",
      projectId: "mock-project-1",
      requestedUrl,
      target: "ecommerce_product",
      status: "analyzed",
      platformType: "shopify",
      pageType: "product_detail",
      riskLevel: "low",
      analyzedAt,
      createdAt: analyzedAt,
      latestPlan: extractionPlan,
    },
    extractionPlan,
    siteAnalysisCreated: true,
    extractionPlanCreated: true,
    runStarted: false,
  };
}

export function getMockAutomationProductDiscovery(url: string): AutomationProductDiscovery {
  const requestedUrl = url.trim() || "https://shop.example/collections/summer-bags";
  return {
    requestedUrl,
    analyzedAt: new Date().toISOString(),
    authorizationConfirmed: true,
    platformProfile: {
      platformType: requestedUrl.includes("shop") ? "shopify" : "independent_ecommerce",
      confidence: 0.86,
      indicators: ["product URL pattern", "JSON-LD catalog data", "collection listing URL"],
      riskLevel: "low",
    },
    pageStructure: {
      pageType: "collection_listing",
      title: "Summer Bags",
      canonicalUrl: requestedUrl,
      linkCount: 42,
      productLinkCount: 12,
      jsonldUrlCount: 3,
      sitemapUrlCount: 0,
      scriptCount: 8,
      textSample:
        "Summer Bags collection page exposes product cards, product links, titles, and canonical product URLs.",
    },
    productCandidates: [
      {
        url: "https://shop.example/products/demo-bag",
        title: "Demo Carry Bag",
        source: "json_ld",
        confidence: 0.9,
      },
      {
        url: "https://shop.example/products/weekend-tote",
        title: "Weekend Tote",
        source: "anchor",
        confidence: 0.86,
      },
      {
        url: "https://shop.example/collections/summer-bags/products/city-pack",
        title: "City Pack",
        source: "anchor",
        confidence: 0.9,
      },
    ],
    toolRecommendations: [
      {
        tool: "ecommerce_product_discovery",
        collectorType: "ecommerce_product_discovery",
        fit: "primary",
        riskLevel: "low",
        reason: "集合页已经暴露商品 URL，可先建立候选商品池，再人工确认是否批量进入商品页采集。",
      },
      {
        tool: "ecommerce_product_page",
        collectorType: "ecommerce_product_page",
        fit: "next_step",
        riskLevel: "low",
        reason: "候选商品 URL 确认后，下一步进入商品详情页字段解析。",
      },
    ],
    discoveryPlan: {
      nextCollectorType: "ecommerce_product_page",
      candidateCount: 3,
      maxProducts: 50,
      fanOutRequiresReview: true,
    },
    sourceDraft: {
      type: "ecommerce_product_discovery",
      config: {
        url: requestedUrl,
        max_products: 50,
        platform_hint: "shopify",
      },
      suggestedName: "商品链接发现：Summer Bags",
      scheduleCron: null,
    },
    blockedReasons: [],
  };
}

export function getMockAutomationProductFanoutPreview(
  input: AutomationProductFanoutPreviewInput,
): AutomationProductFanoutPreview {
  const selected = input.candidates.slice(0, input.maxSources ?? 20);
  const candidateStatuses = selected.map((candidate, index) => {
    const blocked = index > 0 && selected.findIndex((item) => item.url === candidate.url) < index;
    return {
      url: candidate.url,
      title: candidate.title ?? null,
      source: candidate.source ?? null,
      confidence: candidate.confidence ?? null,
      status: blocked ? "blocked" as const : "ready" as const,
      reason: blocked ? "duplicate_candidate_url" : null,
    };
  });
  const readyCandidates = candidateStatuses.filter((candidate) => candidate.status === "ready");
  const fields = input.fields ?? ["title", "price", "currency", "availability", "sku", "brand", "canonical_url"];
  return {
    requestedParentUrl: input.parentUrl,
    analyzedAt: new Date().toISOString(),
    authorizationConfirmed: input.authorized,
    candidateStatuses,
    sourceDrafts: readyCandidates.map((candidate) => ({
      type: "ecommerce_product_page",
      config: {
        url: candidate.url,
        fields,
        platform_hint: "auto",
      },
      suggestedName: `商品页采集：${candidate.title ?? candidate.url}`,
      scheduleCron: null,
    })),
    batchPlan: {
      runMode: "preview_only",
      nextCollectorType: "ecommerce_product_page",
      readyCount: readyCandidates.length,
      blockedCount: candidateStatuses.length - readyCandidates.length,
      maxSources: input.maxSources ?? 20,
      fields,
      manualReviewRequired: true,
      executionBoundary: "preview_only_no_database_write",
    },
    blockedReasons: [
      "当前结果仅为预览，尚未创建真实采集源、任务或采集运行。",
    ],
  };
}

export function getMockAutomationProductFanoutCreate(
  input: AutomationProductFanoutCreateInput,
): AutomationProductFanoutCreate {
  const preview = getMockAutomationProductFanoutPreview(input);
  const now = new Date().toISOString();
  return {
    requestedParentUrl: input.parentUrl,
    createdAt: now,
    authorizationConfirmed: input.authorized,
    persistedSources: preview.sourceDrafts.map((draft, index) => {
      const url = String(draft.config.url ?? "");
      return {
        url,
        action: "created",
        source: {
          id: `source_fanout_${index + 1}`,
          projectId: input.projectId,
          name: draft.suggestedName,
          type: draft.type,
          url,
          enabled: input.enableTasks ?? true,
          config: draft.config,
          scheduleCron: null,
          createdAt: now,
          updatedAt: now,
        },
        task: (input.enableTasks ?? true)
          ? {
              id: `task_fanout_${index + 1}`,
              sourceId: `source_fanout_${index + 1}`,
              collectorType: "ecommerce_product_page",
              name: draft.suggestedName,
              status: "enabled",
              scheduleCron: null,
            }
          : null,
      };
    }),
    candidateStatuses: preview.candidateStatuses,
    summary: {
      createdSources: preview.sourceDrafts.length,
      reusedSources: 0,
      enabledTasks: input.enableTasks === false ? 0 : preview.sourceDrafts.length,
      blockedCandidates: preview.batchPlan.blockedCount,
      runStarted: false,
    },
    auditEvents: [
      {
        event: "fanout_create_requested",
        preview_ready_count: preview.batchPlan.readyCount,
        enable_tasks: input.enableTasks ?? true,
      },
      ...preview.sourceDrafts.map((draft) => ({
        event: "fanout_source_persisted",
        url: draft.config.url,
        action: "created",
        run_started: false,
      })),
    ],
    blockedReasons: [
      "已完成持久化创建或复用，但尚未启动任何采集运行。",
    ],
  };
}

export function getMockAutomationProductBatchRun(
  input: AutomationProductBatchRunInput,
): AutomationProductBatchRun {
  const now = new Date().toISOString();
  const items = input.taskIds.slice(0, input.maxTasks ?? 5).map((taskId, index) => {
    const complete = index % 2 === 0;
    const configuredFields = ["title", "price", "sku", "canonical_url"];
    const fieldValues = complete
      ? {
          title: "Demo Carry Bag",
          price: 129.9,
          sku: "BAG-001",
          canonical_url: "https://shop.example/products/demo-bag",
        }
      : {
          title: "Weekend Tote",
          canonical_url: "https://shop.example/products/weekend-tote",
        };
    const extractedFields = configuredFields.filter((field) => field in fieldValues);
    const missingFields = configuredFields.filter((field) => !(field in fieldValues));
    const completenessPercent = Math.round((extractedFields.length / configuredFields.length) * 100);
    return {
      taskId,
      taskName: index === 0 ? "商品页采集：Demo Carry Bag" : "商品页采集：Weekend Tote",
      sourceId: `source_fanout_${index + 1}`,
      sourceUrl:
        index === 0
          ? "https://shop.example/products/demo-bag"
          : "https://shop.example/products/weekend-tote",
      status: "run_completed" as const,
      blockedReason: null,
      run: {
        id: `run_batch_${index + 1}`,
        taskId,
        status: "success",
        recordsCount: 1,
        entitiesCount: 1,
        errorMessage: null,
        startedAt: now,
        finishedAt: now,
      },
      recordsCount: 1,
      entitiesCount: 1,
      fieldCompleteness: {
        configuredFields,
        extractedFields,
        missingFields,
        fieldValues,
        completenessRatio: completenessPercent / 100,
        completenessPercent,
      },
      errorMessage: null,
    };
  });
  const average = items.length
    ? Math.round(
        items.reduce((total, item) => total + (item.fieldCompleteness?.completenessPercent ?? 0), 0)
        / items.length,
      )
    : 0;
  return {
    createdAt: now,
    authorizationConfirmed: input.authorized,
    items,
    summary: {
      requestedTasks: input.taskIds.length,
      runTasks: items.length,
      blockedTasks: Math.max(input.taskIds.length - items.length, 0),
      successfulRuns: items.length,
      failedRuns: 0,
      recordsCount: items.reduce((total, item) => total + item.recordsCount, 0),
      entitiesCount: items.reduce((total, item) => total + item.entitiesCount, 0),
      averageCompletenessPercent: average,
      runStarted: items.length > 0,
    },
    auditEvents: [
      {
        event: "product_batch_run_requested",
        requested_tasks: input.taskIds.length,
      },
      ...items.map((item) => ({
        event: "product_batch_task_run_completed",
        task_id: item.taskId,
        completeness_percent: item.fieldCompleteness?.completenessPercent,
      })),
    ],
    blockedReasons: ["本次仅执行用户确认的小批量任务，没有创建调度或自动循环。"],
  };
}

export function getMockAutomationProductDatasetPreview(
  input: AutomationProductDatasetPreviewInput,
): AutomationProductDatasetPreview {
  const fields = input.fields ?? ["title", "price", "sku", "canonical_url"];
  const sourceRows = [
    {
      title: "Demo Carry Bag",
      price: 129.9,
      sku: "BAG-001",
      canonical_url: "https://shop.example/products/demo-bag",
    },
    {
      title: "Weekend Tote",
      canonical_url: "https://shop.example/products/weekend-tote",
    },
  ];
  const rows = sourceRows.slice(0, input.maxRows ?? 100).map((values, index) => {
    const filteredValues = Object.fromEntries(
      fields
        .filter((field) => field in values)
        .map((field) => [field, values[field as keyof typeof values]]),
    );
    const missingFields = fields.filter((field) => !(field in filteredValues));
    return {
      rowId: `mock-row-${index + 1}`,
      taskRunId: input.taskRunIds[index] ?? input.taskRunIds[0] ?? `run_batch_${index + 1}`,
      rawRecordId: `raw_dataset_${index + 1}`,
      sourceUrl: String(values.canonical_url),
      values: filteredValues,
      missingFields,
      completenessPercent: Math.round((Object.keys(filteredValues).length / fields.length) * 100),
    };
  });
  const average = rows.length
    ? Math.round(rows.reduce((total, row) => total + row.completenessPercent, 0) / rows.length)
    : 0;
  return {
    createdAt: new Date().toISOString(),
    authorizationConfirmed: input.authorized,
    rows,
    summary: {
      requestedRuns: input.taskRunIds.length,
      matchedRuns: Math.min(input.taskRunIds.length, rows.length),
      rowsCount: rows.length,
      selectedFields: fields,
      averageCompletenessPercent: average,
      exportFormat: "json",
      exportReady: rows.length > 0,
    },
    cleaningScriptDraft: [
      "drop rows where title is empty",
      "trim string fields and collapse repeated whitespace",
      "cast price to decimal when present",
      "normalize canonical_url and image_url as absolute URL strings",
      "keep missing values explicit as null for downstream review",
    ],
    exportPreview: {
      format: "json",
      schema: {
        fields,
        primary_key: "canonical_url",
        missing_value_policy: "explicit_null",
      },
      rows: rows.map((row) =>
        Object.fromEntries(fields.map((field) => [field, row.values[field] ?? null])),
      ),
    },
    auditEvents: [
      {
        event: "product_dataset_preview_requested",
        requested_runs: input.taskRunIds.length,
      },
    ],
    blockedReasons: ["当前为只读数据集预览，尚未保存 Dataset 或写出导出文件。"],
  };
}

export function getMockAutomationProductDatasetSave(
  input: AutomationProductDatasetSaveInput,
): AutomationProductDatasetSave {
  const preview = getMockAutomationProductDatasetPreview(input);
  const now = new Date().toISOString();
  const normalizedName = input.name.trim() || "Mock Product Dataset";
  const datasetId = `dataset_${normalizedName.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`;
  return {
    savedAt: now,
    authorizationConfirmed: input.authorized,
    dataset: {
      id: datasetId,
      projectId: "proj_ecommerce",
      name: normalizedName,
      datasetType: "ecommerce_product",
      status: "active",
      description: input.description ?? null,
    },
    version: {
      id: `${datasetId}_v1`,
      datasetId,
      cleaningPlanId: input.cleaningPlanId ?? null,
      versionNumber: 1,
      sourceTaskRunIds: input.taskRunIds,
      selectedFields: preview.summary.selectedFields,
      cleaningScript: preview.cleaningScriptDraft,
      rowCount: preview.summary.rowsCount,
      averageCompletenessPercent: preview.summary.averageCompletenessPercent,
      status: "saved",
      createdAt: now,
      exportPreview: preview.exportPreview,
    },
    auditEvents: [
      {
        event: "product_dataset_version_saved",
        dataset_id: datasetId,
        version_id: `${datasetId}_v1`,
        version_number: 1,
        row_count: preview.summary.rowsCount,
        cleaning_plan_id: input.cleaningPlanId ?? null,
      },
    ],
    blockedReasons: [
      "Dataset 版本已保存；mock 环境尚未写出文件、对象存储导出或自动调度。",
    ],
  };
}

export function getMockAutomationProductScheduleApprove(
  input: AutomationProductScheduleApproveInput,
): AutomationProductScheduleApprove {
  const now = new Date().toISOString();
  const dataset = {
    id: input.datasetId,
    projectId: "proj_ecommerce",
    name: "Training Product Dataset Smoke",
    datasetType: "ecommerce_product",
    status: "active",
    description: "Mock approved dataset.",
  };
  const version = {
    id: input.datasetVersionId,
    datasetId: input.datasetId,
    cleaningPlanId: null,
    versionNumber: 1,
    sourceTaskRunIds: ["run_batch_1", "run_batch_2"],
    selectedFields: ["title", "price", "sku", "canonical_url"],
    cleaningScript: [
      "drop rows where title is empty",
      "trim string fields and collapse repeated whitespace",
    ],
    rowCount: 2,
    averageCompletenessPercent: 75,
    status: "saved",
    createdAt: now,
    exportPreview: { format: "json" },
  };
  const approvedTasks = input.taskIds.map((taskId, index) => ({
    taskId,
    taskName: `商品页采集任务 ${index + 1}`,
    status: "enabled",
    scheduleCron: input.scheduleCron?.trim() || null,
    schedulePolicy: input.schedulePolicy ?? "auto_freshness",
    freshnessTargetHours: input.freshnessTargetHours ?? 24,
    datasetId: input.datasetId,
    datasetVersionId: input.datasetVersionId,
    approvedAt: now,
  }));
  return {
    approvedAt: now,
    authorizationConfirmed: input.authorized,
    dataset,
    version,
    approvedTasks,
    blockedTasks: [],
    summary: {
      requestedTasks: input.taskIds.length,
      approvedTasks: approvedTasks.length,
      blockedTasks: 0,
      runStarted: false,
    },
    auditEvents: [
      {
        event: "product_schedule_approved",
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        approved_tasks: approvedTasks.length,
        run_started: false,
      },
    ],
    blockedReasons: ["调度审批只更新任务配置，不会立即启动采集运行。"],
  };
}

export function getMockAutomationProductDriftCheck(
  input: AutomationProductDriftCheckInput,
): AutomationProductDriftCheck {
  const now = new Date().toISOString();
  const dataset = {
    id: input.datasetId,
    projectId: "proj_ecommerce",
    name: "Training Product Dataset Smoke",
    datasetType: "ecommerce_product",
    status: "active",
    description: "Mock approved dataset.",
  };
  const version = {
    id: input.datasetVersionId,
    datasetId: input.datasetId,
    cleaningPlanId: null,
    versionNumber: 1,
    sourceTaskRunIds: ["run_batch_1", "run_batch_2"],
    selectedFields: ["title", "price", "sku", "canonical_url"],
    cleaningScript: [
      "drop rows where title is empty",
      "trim string fields and collapse repeated whitespace",
    ],
    rowCount: 2,
    averageCompletenessPercent: 75,
    status: "saved",
    createdAt: now,
    exportPreview: { format: "json" },
  };
  const items = input.taskIds.map((taskId, index) => {
    const isCritical = index === 1;
    const status: "critical" | "ok" = isCritical ? "critical" : "ok";
    return {
      taskId,
      taskName: `商品页采集任务 ${index + 1}`,
      sourceUrl: `https://shop.example/products/mock-${index + 1}`,
      status,
      blockedReason: null,
      latestRunId: `run_batch_${index + 1}`,
      latestRunStatus: "success",
      datasetVersionCompletenessPercent: 75,
      latestCompletenessPercent: isCritical ? 50 : 100,
      completenessDropPercent: isCritical ? 25 : 0,
      missingFields: isCritical ? ["price", "sku"] : [],
      newMissingFields: isCritical ? ["price", "sku"] : [],
      freshnessTargetHours: 6,
      staleHours: 0,
      issues: isCritical
        ? ["completeness_drift_exceeded", "approved_fields_missing"]
        : [],
      signalGroups: isCritical
        ? {
            field_missingness: ["missing:price", "missing:sku"],
            repository_coverage: [],
            popularity: [],
            issue_activity: [],
            release_freshness: [],
            commit_freshness: [],
          }
        : {
            field_missingness: [],
            repository_coverage: [],
            popularity: [],
            issue_activity: [],
            release_freshness: [],
            commit_freshness: [],
          },
    };
  });
  const criticalTasks = items.filter((item) => item.status === "critical").length;
  return {
    checkedAt: now,
    authorizationConfirmed: input.authorized,
    dataset,
    version,
    items,
    summary: {
      requestedTasks: input.taskIds.length,
      checkedTasks: input.taskIds.length,
      blockedTasks: 0,
      warningTasks: 0,
      criticalTasks,
      staleTasks: 0,
      missingFieldTasks: criticalTasks,
      runStarted: false,
      alertCreated: false,
    },
    auditEvents: [
      {
        event: "product_drift_check_requested",
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        run_started: false,
        alert_created: false,
      },
    ],
    blockedReasons: ["漂移检查为只读评估，不会启动采集、创建告警或发送通知。"],
  };
}

const mockAutomationDriftEvents: AutomationProductDriftEvent[] = [];
const mockAutomationDatasetExportJobs: AutomationProductDatasetExportJob[] = [
  getDefaultMockDatasetExportJob(),
];
const mockDriftAlertRules: AlertRule[] = [];
const mockDriftSignals: Signal[] = [];
const mockDriftAlertEvents: AlertEvent[] = [];
const mockDriftNotifications: NotificationItem[] = [];

export function getMockAutomationProductDriftEventSave(
  input: AutomationProductDriftEventSaveInput,
): AutomationProductDriftEvent {
  const checked = getMockAutomationProductDriftCheck(input);
  const criticalTasks = checked.summary.criticalTasks;
  const warningTasks = checked.summary.warningTasks + checked.summary.blockedTasks;
  const status: AutomationProductDriftEvent["status"] =
    criticalTasks > 0 ? "critical" : warningTasks > 0 ? "warning" : "ok";
  const event: AutomationProductDriftEvent = {
    id: `drift_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    createdAt: new Date().toISOString(),
    dataset: checked.dataset,
    version: checked.version,
    eventType: "ecommerce_product_drift",
    status,
    thresholds: {
      completeness_drop_threshold_percent: input.completenessDropThresholdPercent ?? 10,
      freshness_grace_hours: input.freshnessGraceHours ?? 0,
    },
    summary: checked.summary,
    items: checked.items,
    auditEvents: [
      ...checked.auditEvents,
      {
        event: "product_drift_event_saved",
        dataset_id: input.datasetId,
        dataset_version_id: input.datasetVersionId,
        run_started: false,
        alert_created: false,
      },
    ],
    note: input.note?.trim() || null,
    runStarted: false,
    alertCreated: false,
  };
  mockAutomationDriftEvents.unshift(event);
  return event;
}

export function getMockAutomationProductDriftEvents(
  input: AutomationProductDriftEventListInput = {},
): AutomationProductDriftEventList {
  const limit = input.limit ?? 20;
  const items = [...mockAutomationDriftEvents, getDefaultMockProductDriftEvent()]
    .filter((event) => !input.datasetId || event.dataset.id === input.datasetId)
    .filter((event) => !input.datasetVersionId || event.version.id === input.datasetVersionId)
    .slice(0, limit);
  return {
    items,
    total: items.length,
    runStarted: false,
    alertCreated: false,
  };
}

export function getMockAutomationProductDatasets(
  input: AutomationProductDatasetListInput = {},
): AutomationProductDatasetList {
  const datasets = getDefaultMockProductDatasetItems()
    .filter((item) => !input.projectId || item.dataset.projectId === input.projectId)
    .slice(0, input.limit ?? 50);
  return {
    items: datasets,
    total: datasets.length,
    runStarted: false,
    alertCreated: false,
  };
}

export function getMockAutomationProductDatasetVersions(
  input: AutomationProductDatasetVersionListInput,
): AutomationProductDatasetVersionList {
  const versionsByDataset = getDefaultMockProductDatasetVersions();
  const datasetItem = getDefaultMockProductDatasetItems().find(
    (item) => item.dataset.id === input.datasetId,
  ) ?? getDefaultMockProductDatasetItems()[0];
  const versions = (versionsByDataset[input.datasetId] ?? versionsByDataset[datasetItem.dataset.id] ?? [])
    .slice(0, input.limit ?? 50);
  return {
    dataset: datasetItem.dataset,
    versions,
    total: versionsByDataset[input.datasetId]?.length ?? versions.length,
    runStarted: false,
    alertCreated: false,
  };
}

export function getMockAutomationProductDatasetExportCreate(
  input: AutomationProductDatasetExportCreateInput,
): AutomationProductDatasetExportJob {
  const dataset = getDefaultMockProductDatasetItems().find(
    (item) => item.dataset.id === input.datasetId,
  )?.dataset ?? getDefaultMockShopifyDataset();
  const version =
    getDefaultMockProductDatasetVersions()[dataset.id]?.find(
      (item) => item.id === input.datasetVersionId,
    ) ?? getDefaultMockProductDatasetVersions().dataset_shopify_price[0];
  const createdAt = new Date().toISOString();
  const id = `export_${createdAt.replace(/[^0-9]/g, "")}_${Math.random()
    .toString(36)
    .slice(2, 8)}`;
  const job: AutomationProductDatasetExportJob = {
    id,
    dataset,
    version,
    exportFormat: input.exportFormat,
    status: input.confirmCreate ? "success" : "blocked",
    filename: `shopify-product-dataset-v${version.versionNumber}.${input.exportFormat}`,
    contentType: exportContentType(input.exportFormat),
    artifactSizeBytes: input.confirmCreate ? 384 : 0,
    rowCount: version.rowCount,
    checksumSha256: "mock".padEnd(64, "0"),
    errorMessage: input.confirmCreate ? null : "dataset_export_confirmation_required",
    createdAt,
    finishedAt: input.confirmCreate ? createdAt : null,
    downloadUrl: input.confirmCreate
      ? `/api/automation/product-datasets/${dataset.id}/versions/${version.id}/exports/${id}/download`
      : null,
    auditEvents: [
      {
        event: "product_dataset_export_file_written",
        export_format: input.exportFormat,
        run_started: false,
      },
    ],
    blockedReasons: [
      "导出文件已写入受控目录；下载接口会再次校验当前账号的数据集权限。",
    ],
  };
  if (input.confirmCreate) {
    mockAutomationDatasetExportJobs.unshift(job);
  }
  return job;
}

export function getMockAutomationProductDatasetExports(
  input: AutomationProductDatasetExportListInput,
): AutomationProductDatasetExportList {
  const items = mockAutomationDatasetExportJobs
    .filter((job) => job.dataset.id === input.datasetId)
    .filter((job) => !input.datasetVersionId || job.version.id === input.datasetVersionId)
    .slice(0, input.limit ?? 20);
  return {
    items,
    total: items.length,
    exportCreated: false,
    runStarted: false,
  };
}

export function getMockAutomationProductDriftAlertPreview(
  input: AutomationProductDriftAlertPreviewInput,
): AutomationProductDriftAlertPreview {
  const dataset = getDefaultMockProductDatasetItems().find(
    (item) => item.dataset.id === input.datasetId,
  )?.dataset ?? getDefaultMockShopifyDataset();
  const latestVersion =
    getDefaultMockProductDatasetVersions()[dataset.id]?.[0] ??
    getDefaultMockProductDatasetVersions().dataset_shopify_price[0];
  const statuses = input.minStatus === "warning" ? ["warning", "critical"] : ["critical"];
  const matchedEvents = getMockAutomationProductDriftEvents({
    datasetId: dataset.id,
    datasetVersionId: input.datasetVersionId ?? latestVersion.id,
    limit: input.limit ?? 20,
  }).items.filter((event) => statuses.includes(event.status));
  return {
    generatedAt: new Date().toISOString(),
    authorizationConfirmed: input.authorized,
    dataset,
    latestVersion,
    ruleDraft: {
      name: input.name?.trim() || `Dataset drift alert: ${dataset.name}`,
      projectId: dataset.projectId,
      signalType: "dataset_drift",
      condition: {
        field: "severity",
        op: "in",
        value: input.minStatus === "warning" ? ["medium", "high"] : ["high"],
        source: "dataset_drift_event",
        dataset_id: dataset.id,
        dataset_version_id: latestVersion.id,
        drift_statuses: statuses,
        event_type: "ecommerce_product_drift",
      },
      channel: input.channel ?? "in_app",
      enabled: input.enabled ?? true,
    },
    matchedEvents,
    summary: {
      matchedEvents: matchedEvents.length,
      criticalEvents: matchedEvents.filter((event) => event.status === "critical").length,
      warningEvents: matchedEvents.filter((event) => event.status === "warning").length,
      alertRuleCreated: false,
      signalCreated: false,
      alertEventCreated: false,
      notificationCreated: false,
      runStarted: false,
    },
    blockedReasons: [
      "告警策略预览只读取已保存 DriftEvent，不会创建 AlertRule、Signal、AlertEvent 或通知。",
    ],
  };
}

export function getMockAutomationProductDriftAlertRuleCreate(
  input: AutomationProductDriftAlertRuleCreateInput,
): AutomationProductDriftAlertRuleCreate {
  const preview = getMockAutomationProductDriftAlertPreview(input);
  const alertRule: AlertRule = {
    id: `rule_drift_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    workspaceId: "workspace_mock",
    projectId: preview.ruleDraft.projectId,
    name: preview.ruleDraft.name,
    signalType: preview.ruleDraft.signalType,
    condition: preview.ruleDraft.condition,
    channel: preview.ruleDraft.channel,
    enabled: preview.ruleDraft.enabled,
    createdAt: new Date().toISOString(),
  };
  if (input.confirmCreate) {
    mockDriftAlertRules.unshift(alertRule);
  }
  return {
    ...preview,
    generatedAt: new Date().toISOString(),
    summary: {
      ...preview.summary,
      alertRuleCreated: Boolean(input.confirmCreate),
      signalCreated: false,
      alertEventCreated: false,
      notificationCreated: false,
      runStarted: false,
    },
    blockedReasons: [
      "已创建 DriftEvent 告警策略；本次不会回放历史事件、创建 Signal、AlertEvent 或发送通知。",
      "后续需要 DatasetDrift 信号桥接后，规则才会进入现有 AlertEvent 生成链路。",
    ],
    alertRule,
  };
}

export function getMockAutomationProductDriftAlertEventCreate(
  input: AutomationProductDriftAlertEventCreateInput,
): AutomationProductDriftAlertEventCreate {
  const datasetItem = getDefaultMockProductDatasetItems().find(
    (item) => item.dataset.id === input.datasetId,
  );
  const dataset = datasetItem?.dataset ?? getDefaultMockShopifyDataset();
  const version =
    getDefaultMockProductDatasetVersions()[dataset.id]?.find(
      (item) => item.id === input.datasetVersionId,
    ) ?? getDefaultMockProductDatasetVersions().dataset_shopify_price[0];
  const driftEvent =
    getMockAutomationProductDriftEvents({
      datasetId: dataset.id,
      datasetVersionId: version.id,
      limit: 20,
    }).items.find((event) => event.id === input.driftEventId) ??
    getDefaultMockProductDriftEvent();
  const existingSignal = mockDriftSignals.find(
    (signal) => signal.metadata.drift_event_id === driftEvent.id,
  );
  const signalCreated = !existingSignal && input.confirmCreate;
  const signal: Signal =
    existingSignal ?? {
      id: `signal_drift_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      workspaceId: "workspace_mock",
      projectId: dataset.projectId,
      entityId: `entity_${dataset.id}`,
      signalType: "dataset_drift",
      previousSnapshotId: `snapshot_${version.id}_baseline`,
      currentSnapshotId: `snapshot_${driftEvent.id}`,
      previousValue: 0,
      currentValue: driftEvent.summary.criticalTasks || driftEvent.summary.missingFieldTasks,
      delta: driftEvent.summary.criticalTasks || driftEvent.summary.missingFieldTasks,
      deltaRatio: null,
      confidence: driftEvent.status === "critical" ? 90 : 80,
      severity: driftEvent.status === "critical" ? "high" : "medium",
      detectedAt: new Date().toISOString(),
      metadata: {
        source: "dataset_drift_event",
        dataset_id: dataset.id,
        dataset_version_id: version.id,
        drift_event_id: driftEvent.id,
        event_type: driftEvent.eventType,
        status: driftEvent.status,
      },
    };
  if (signalCreated) {
    mockDriftSignals.unshift(signal);
  }
  const matchedRule = mockDriftAlertRules.find(
    (rule) =>
      rule.signalType === "dataset_drift" &&
      rule.projectId === dataset.projectId &&
      rule.condition.source === "dataset_drift_event" &&
      rule.condition.dataset_id === dataset.id &&
      (rule.condition.dataset_version_id === version.id ||
        rule.condition.dataset_version_id === null) &&
      Array.isArray(rule.condition.value) &&
      rule.condition.value.includes(signal.severity),
  );
  const existingAlertEvent = mockDriftAlertEvents.find(
    (event) => event.signalId === signal.id && event.ruleId === matchedRule?.id,
  );
  const alertEventCreated = Boolean(input.confirmCreate && matchedRule && !existingAlertEvent);
  const alertEvent: AlertEvent | null =
    existingAlertEvent ??
    (matchedRule
      ? {
          id: `event_drift_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
          ruleId: matchedRule.id,
          signalId: signal.id,
          status: "triggered",
          payload: {
            rule_name: matchedRule.name,
            signal_type: signal.signalType,
            severity: signal.severity,
            project_id: dataset.projectId,
            source: "dataset_drift_event",
            dataset_id: dataset.id,
            dataset_version_id: version.id,
            drift_event_id: driftEvent.id,
            event_type: driftEvent.eventType,
          },
          triggeredAt: new Date().toISOString(),
          sentAt: null,
        }
      : null);
  if (alertEventCreated && alertEvent) {
    mockDriftAlertEvents.unshift(alertEvent);
  }
  return {
    generatedAt: new Date().toISOString(),
    authorizationConfirmed: input.authorized,
    dataset,
    version,
    driftEvent,
    signal,
    alertEvents: alertEventCreated && alertEvent ? [alertEvent] : [],
    summary: {
      matchedEvents: 1,
      criticalEvents: driftEvent.status === "critical" ? 1 : 0,
      warningEvents: driftEvent.status === "warning" ? 1 : 0,
      alertRuleCreated: false,
      signalCreated,
      alertEventCreated,
      notificationCreated: false,
      runStarted: false,
    },
    blockedReasons: [
      "本次只桥接已保存 DriftEvent 到 Signal/AlertEvent；不会启动采集、创建 TaskRun、发送通知或写出文件。",
    ],
  };
}

export function getMockAutomationProductDriftAlertNotificationSend(
  input: AutomationProductDriftAlertNotificationSendInput,
): AutomationProductDriftAlertNotificationSend {
  if (!input.confirmSend) {
    throw new Error("drift_alert_notification_confirmation_required");
  }
  const dataset = getDefaultMockShopifyDataset();
  const [version] = getDefaultMockProductDatasetVersions().dataset_shopify_price;
  const driftEvent =
    mockAutomationDriftEvents.find((event) => event.id === input.driftEventId) ??
    getDefaultMockProductDriftEvent();
  const requestedAlertEvents = mockDriftAlertEvents.filter((event) =>
    input.alertEventIds.includes(event.id),
  );
  let createdNotifications = 0;
  const notifications: NotificationItem[] = requestedAlertEvents.map((event) => {
    const existing = mockDriftNotifications.find(
      (notification) => notification.referenceId === event.id,
    );
    if (existing) {
      event.status = "sent";
      event.sentAt = event.sentAt ?? new Date().toISOString();
      return existing;
    }
    const notification: NotificationItem = {
      id: `notification_drift_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      userId: "user_mock",
      title: `数据集漂移告警：${dataset.name}`,
      body: `${driftEvent.eventType} 已命中告警事件；状态 ${driftEvent.status}，请复核字段完整率与刷新策略。`,
      notificationType: "alert",
      referenceType: "alert_event",
      referenceId: event.id,
      isRead: false,
      createdAt: new Date().toISOString(),
    };
    event.status = "sent";
    event.sentAt = event.sentAt ?? notification.createdAt;
    mockDriftNotifications.unshift(notification);
    createdNotifications += 1;
    return notification;
  });
  return {
    generatedAt: new Date().toISOString(),
    authorizationConfirmed: input.authorized,
    dataset,
    version,
    driftEvent,
    alertEvents: requestedAlertEvents,
    notifications,
    summary: {
      matchedEvents: requestedAlertEvents.length,
      criticalEvents: driftEvent.status === "critical" ? requestedAlertEvents.length : 0,
      warningEvents: driftEvent.status === "warning" ? requestedAlertEvents.length : 0,
      alertRuleCreated: false,
      signalCreated: false,
      alertEventCreated: false,
      notificationCreated: createdNotifications > 0,
      runStarted: false,
    },
    blockedReasons: [
      "本次只发送已生成 AlertEvent 的站内通知；不会启动采集、创建 TaskRun、发送邮件、修改调度或写出文件。",
    ],
  };
}

export function getMockAutomationProductDriftAlertEmailSend(
  input: AutomationProductDriftAlertEmailSendInput,
): AutomationProductDriftAlertEmailSend {
  if (!input.confirmSend) {
    throw new Error("drift_alert_email_confirmation_required");
  }
  const dataset = getDefaultMockShopifyDataset();
  const [version] = getDefaultMockProductDatasetVersions().dataset_shopify_price;
  const driftEvent =
    mockAutomationDriftEvents.find((event) => event.id === input.driftEventId) ??
    getDefaultMockProductDriftEvent();
  const requestedAlertEvents = mockDriftAlertEvents.filter((event) =>
    input.alertEventIds.includes(event.id),
  );
  if (requestedAlertEvents.length === 0) {
    return {
      generatedAt: new Date().toISOString(),
      authorizationConfirmed: input.authorized,
      dataset,
      version,
      driftEvent,
      alertEvents: [],
      emailDeliveries: [],
      summary: {
        matchedEvents: 0,
        criticalEvents: 0,
        warningEvents: 0,
        alertRuleCreated: false,
        signalCreated: false,
        alertEventCreated: false,
        notificationCreated: false,
        runStarted: false,
      },
      blockedReasons: ["未检测到匹配的 AlertEvent，未发起邮件告警。"],
    };
  }

  const existingDeliveryIds = new Set<string>();
  const emailDeliveries = requestedAlertEvents.map((event) => {
    const eventId = event.id;
    const signal = mockDriftSignals.find((item) => item.id === event.signalId);
    const rule = mockDriftAlertRules.find((ruleItem) => ruleItem.id === event.ruleId);
    if (!rule || !signal) {
      return {
        alertEventId: eventId,
        recipientEmail: input.recipientEmail ?? "demo@example.com",
        delivered: false,
        deliveredAt: null,
        reason: "missing_rule_or_signal",
      };
    }
    if (rule.channel !== "email" && rule.channel !== "both") {
      return {
        alertEventId: eventId,
        recipientEmail: input.recipientEmail ?? "demo@example.com",
        delivered: false,
        deliveredAt: null,
        reason: "alert_event_channel_not_email",
      };
    }
    const deliveryId = `${event.signalId}:${eventId}`;
    const matched = existingDeliveryIds.has(deliveryId);
    existingDeliveryIds.add(deliveryId);
    return {
      alertEventId: eventId,
      recipientEmail: input.recipientEmail ?? "demo@example.com",
      delivered: !matched,
      deliveredAt: matched ? null : new Date().toISOString(),
      reason: matched ? "already_delivered" : null,
    };
  });

  return {
    generatedAt: new Date().toISOString(),
    authorizationConfirmed: input.authorized,
    dataset,
    version,
    driftEvent,
    alertEvents: requestedAlertEvents,
    emailDeliveries,
    summary: {
      matchedEvents: requestedAlertEvents.length,
      criticalEvents: driftEvent.status === "critical" ? requestedAlertEvents.length : 0,
      warningEvents: driftEvent.status === "warning" ? requestedAlertEvents.length : 0,
      alertRuleCreated: false,
      signalCreated: false,
      alertEventCreated: false,
      notificationCreated: false,
      runStarted: false,
    },
    blockedReasons: [
      "本次只发送已生成 AlertEvent 的邮件告警；不会启动采集、创建 TaskRun、发送站内通知、修改调度或写出文件。",
    ],
  };
}

function getDefaultMockProductDatasetItems(): AutomationProductDatasetList["items"] {
  const shopifyDataset = getDefaultMockShopifyDataset();
  const [latestVersion] = getDefaultMockProductDatasetVersions().dataset_shopify_price;
  const latestSavedEvent = mockAutomationDriftEvents.find(
    (event) => event.dataset.id === "dataset_shopify_price",
  );
  return [
    {
      dataset: shopifyDataset,
      latestVersion,
      versionCount: 2,
      latestDriftEvent: latestSavedEvent ?? getDefaultMockProductDriftEvent(),
      driftEventCount: 1 + mockAutomationDriftEvents.filter(
        (event) => event.dataset.id === "dataset_shopify_price",
      ).length,
    },
    {
      dataset: {
        id: "dataset_brand_catalog",
        projectId: "project_competitor",
        name: "竞品官网目录数据集",
        datasetType: "ecommerce_product",
        status: "active",
        description: "用于沉淀竞品官网公开商品目录和 URL 字段，后续可接入价格与库存监控。",
      },
      latestVersion: null,
      versionCount: 0,
      latestDriftEvent: null,
      driftEventCount: 0,
    },
  ];
}

function getDefaultMockProductDatasetVersions(): Record<string, AutomationProductDatasetVersionList["versions"]> {
  return {
    dataset_shopify_price: [
      {
        id: "dataset_shopify_price_v2",
        datasetId: "dataset_shopify_price",
        cleaningPlanId: null,
        versionNumber: 2,
        sourceTaskRunIds: ["run_batch_1", "run_batch_2"],
        selectedFields: ["title", "price", "sku", "canonical_url"],
        cleaningScript: [
          "drop rows where title is empty",
          "trim string fields and collapse repeated whitespace",
          "cast price to decimal when present",
          "normalize canonical_url and image_url as absolute URL strings",
          "keep missing values explicit as null for downstream review",
        ],
        rowCount: 2,
        averageCompletenessPercent: 75,
        status: "saved",
        createdAt: "2026-06-18T09:20:00.000Z",
        exportPreview: {
          format: "json",
          schema: {
            fields: ["title", "price", "sku", "canonical_url"],
            primary_key: "canonical_url",
            missing_value_policy: "explicit_null",
          },
          rows: [
            {
              title: "Demo Carry Bag",
              price: 129.9,
              sku: "BAG-001",
              canonical_url: "https://shop.example/products/demo-bag",
            },
            {
              title: "Weekend Tote",
              price: null,
              sku: null,
              canonical_url: "https://shop.example/products/weekend-tote",
            },
          ],
        },
      },
      {
        id: "dataset_shopify_price_v1",
        datasetId: "dataset_shopify_price",
        cleaningPlanId: null,
        versionNumber: 1,
        sourceTaskRunIds: ["run_batch_1"],
        selectedFields: ["title", "price", "canonical_url"],
        cleaningScript: [
          "drop rows where title is empty",
          "trim string fields and collapse repeated whitespace",
          "cast price to decimal when present",
        ],
        rowCount: 1,
        averageCompletenessPercent: 100,
        status: "saved",
        createdAt: "2026-06-18T08:30:00.000Z",
        exportPreview: {
          format: "json",
          schema: {
            fields: ["title", "price", "canonical_url"],
            primary_key: "canonical_url",
          },
          rows: [
            {
              title: "Demo Carry Bag",
              price: 129.9,
              canonical_url: "https://shop.example/products/demo-bag",
            },
          ],
        },
      },
    ],
    dataset_brand_catalog: [],
  };
}

function getDefaultMockDatasetExportJob(): AutomationProductDatasetExportJob {
  const dataset = getDefaultMockShopifyDataset();
  const version = getDefaultMockProductDatasetVersions().dataset_shopify_price[0];
  return {
    id: "export_shopify_price_v2_csv",
    dataset,
    version,
    exportFormat: "csv",
    status: "success",
    filename: "shopify-product-dataset-v2.csv",
    contentType: exportContentType("csv"),
    artifactSizeBytes: 384,
    rowCount: version.rowCount,
    checksumSha256: "mock".padEnd(64, "0"),
    errorMessage: null,
    createdAt: "2026-06-18T10:20:00.000Z",
    finishedAt: "2026-06-18T10:20:00.000Z",
    downloadUrl:
      "/api/automation/product-datasets/dataset_shopify_price/versions/dataset_shopify_price_v2/exports/export_shopify_price_v2_csv/download",
    auditEvents: [
      {
        event: "product_dataset_export_file_written",
        export_format: "csv",
        run_started: false,
      },
    ],
    blockedReasons: [
      "导出文件已写入受控目录；下载接口会再次校验当前账号的数据集权限。",
    ],
  };
}

function getDefaultMockProductDriftEvent(): AutomationProductDriftEvent {
  const dataset = getDefaultMockShopifyDataset();
  const version = getDefaultMockProductDatasetVersions().dataset_shopify_price[0];
  return {
    id: "drift_shopify_price_critical",
    createdAt: "2026-06-18T10:05:00.000Z",
    dataset,
    version,
    eventType: "ecommerce_product_drift",
    status: "critical",
    thresholds: {
      completeness_drop_threshold_percent: 10,
      freshness_grace_hours: 24,
    },
    summary: {
      requestedTasks: 2,
      checkedTasks: 2,
      blockedTasks: 0,
      warningTasks: 0,
      criticalTasks: 1,
      staleTasks: 0,
      missingFieldTasks: 1,
      runStarted: false,
      alertCreated: false,
    },
    items: [
      {
        taskId: "task_fanout_1",
        taskName: "商品页采集：Demo Carry Bag",
        sourceUrl: "https://shop.example/products/demo-bag",
        status: "ok",
        blockedReason: null,
        latestRunId: "run_batch_1",
        latestRunStatus: "success",
        datasetVersionCompletenessPercent: 75,
        latestCompletenessPercent: 100,
        completenessDropPercent: 0,
        missingFields: [],
        newMissingFields: [],
        freshnessTargetHours: 6,
        staleHours: 0,
        issues: [],
        signalGroups: {
          field_missingness: [],
          repository_coverage: [],
          popularity: [],
          issue_activity: [],
          release_freshness: [],
          commit_freshness: [],
        },
      },
      {
        taskId: "task_fanout_2",
        taskName: "商品页采集：Weekend Tote",
        sourceUrl: "https://shop.example/products/weekend-tote",
        status: "critical",
        blockedReason: null,
        latestRunId: "run_batch_2",
        latestRunStatus: "success",
        datasetVersionCompletenessPercent: 75,
        latestCompletenessPercent: 50,
        completenessDropPercent: 25,
        missingFields: ["price", "sku"],
        newMissingFields: ["price", "sku"],
        freshnessTargetHours: 6,
        staleHours: 0,
        issues: ["completeness_drift_exceeded", "approved_fields_missing"],
        signalGroups: {
          field_missingness: ["missing:price", "missing:sku"],
          repository_coverage: [],
          popularity: [],
          issue_activity: [],
          release_freshness: [],
          commit_freshness: [],
        },
      },
    ],
    auditEvents: [
      {
        event: "product_drift_event_saved",
        dataset_id: "dataset_shopify_price",
        dataset_version_id: "dataset_shopify_price_v2",
        run_started: false,
        alert_created: false,
      },
    ],
    note: "示例：Weekend Tote 最近一次采集缺少价格和 SKU，需要复核字段解析。",
    runStarted: false,
    alertCreated: false,
  };
}

function getDefaultMockShopifyDataset(): AutomationProductDatasetList["items"][number]["dataset"] {
  return {
    id: "dataset_shopify_price",
    projectId: "project_marketplace_price",
    name: "Shopify 商品价格数据集",
    datasetType: "ecommerce_product",
    status: "active",
    description: "从集合页发现商品 URL 后，对商品页进行字段抽取、清洗和质量留痕。",
  };
}

function exportContentType(format: AutomationDatasetExportFormat) {
  if (format === "json") {
    return "application/json; charset=utf-8";
  }
  if (format === "jsonl") {
    return "application/x-ndjson; charset=utf-8";
  }
  return "text/csv; charset=utf-8";
}

function mockNextRunAt(lastRunAt: string | null, targetHours: number) {
  if (!lastRunAt) {
    return new Date().toISOString();
  }
  return new Date(new Date(lastRunAt).getTime() + targetHours * 60 * 60_000).toISOString();
}

export function getMockTaskRun(taskId: string): TaskRun {
  if (taskId.includes("github_topic")) {
    return {
      id: `run_${Date.now()}`,
      taskId,
      status: "success",
      startedAt: new Date().toISOString(),
      finishedAt: new Date().toISOString(),
      recordsCount: 20,
      entitiesCount: 20,
      errorMessage: null,
      createdAt: new Date().toISOString(),
      logs: [
        { step: "task_run_created", message: "Manual GitHub topic run requested." },
        { step: "github_topic_collected", message: "Collected public repositories for topic web-scraping." },
        { step: "snapshots_saved", message: "Saved repository snapshots for review." },
      ],
    };
  }

  if (taskId === "task_linkedin_company") {
    return {
      id: `run_${Date.now()}`,
      taskId,
      status: "success",
      startedAt: new Date().toISOString(),
      finishedAt: new Date().toISOString(),
      recordsCount: 42,
      entitiesCount: 12,
      errorMessage: null,
      createdAt: new Date().toISOString(),
      logs: [
        { step: "task_run_created", message: "Manual retry requested for LinkedIn company feed." },
        { step: "rate_limit_window_checked", message: "Previous 429 window has expired." },
        { step: "records_collected", message: "Collected 42 company activity records." },
        { step: "signals_evaluated", message: "Resolved data_quality_anomaly and created 2 new signals." },
      ],
    };
  }

  return {
    id: `run_${Date.now()}`,
    taskId,
    status: "success",
    startedAt: new Date().toISOString(),
    finishedAt: new Date().toISOString(),
    recordsCount: 1,
    entitiesCount: 1,
    errorMessage: null,
    createdAt: new Date().toISOString(),
    logs: [
      { step: "task_run_created", message: "Manual run requested." },
      { step: "manual_json_collected", message: "Collected manual JSON payload." },
      { step: "raw_records_stored", message: "Stored 1 new raw records." },
      { step: "entities_normalized", message: "Created 1 snapshots." },
    ],
  };
}

export function getMockRawRecords(): RawRecord[] {
  return [
    {
      id: "raw_competitor_page",
      workspaceId: "workspace_mock",
      projectId: "project_competitor",
      sourceId: "source_competitor_homepage",
      taskRunId: "run_competitor_page_20260611",
      recordType: "generic_web",
      sourceUrl: "https://example.com/pricing",
      contentHash: "a8f1c6c6c1e14f67d2418b1a0ad0fdde4f6e8a029dd8f8aa9b6ef7a8e3124497",
      screenshotUrl: "https://dummyimage.com/900x520/e5e7eb/111827&text=Pricing+Snapshot",
      collectedAt: "2026-06-11T07:20:00.000Z",
      createdAt: "2026-06-11T07:20:00.000Z",
      content: {
        provider: "generic_web",
        kind: "html_snapshot",
        url: "https://example.com/pricing",
        title: "Pricing - Example",
        headline: "New annual plan",
        pricing: "Team plan changed",
        text_length: 1490,
        extracted_text:
          "Example introduced a new annual plan, adjusted team pricing, and moved enterprise messaging above the fold.",
      },
    },
    {
      id: "raw_competitor_page_old",
      workspaceId: "workspace_mock",
      projectId: "project_competitor",
      sourceId: "source_competitor_homepage",
      taskRunId: "run_competitor_page_20260610",
      recordType: "generic_web",
      sourceUrl: "https://example.com/pricing",
      contentHash: "6b9450c1d3f544a58a9e8d736bb40d237df59ec8f87241b030395a4bc7b9b3da",
      screenshotUrl: "https://dummyimage.com/900x520/f3f4f6/374151&text=Pricing+Snapshot+Old",
      collectedAt: "2026-06-10T07:20:00.000Z",
      createdAt: "2026-06-10T07:20:00.000Z",
      content: {
        provider: "generic_web",
        kind: "html_snapshot",
        url: "https://example.com/pricing",
        title: "Pricing - Example",
        headline: "Team plan",
        pricing: "Monthly only",
        text_length: 1080,
        extracted_text:
          "Example promoted monthly team pricing and kept enterprise inquiry content below primary pricing cards.",
      },
    },
    {
      id: "raw_codex_repo",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      sourceId: "source_codex_repo",
      taskRunId: "run_codex_repo_20260611",
      recordType: "github_repo",
      sourceUrl: "https://github.com/openai/codex",
      contentHash: "f9b9290ad4ce7ce6e1b9c4e01c308f6a19e7c5e06f19e842bb8f16b87fe8c02a",
      screenshotUrl: null,
      collectedAt: "2026-06-11T08:05:00.000Z",
      createdAt: "2026-06-11T08:05:00.000Z",
      content: {
        provider: "github",
        kind: "repo_snapshot",
        full_name: "openai/codex",
        stars: 260,
        forks: 42,
        open_issues: 8,
        default_branch: "main",
      },
    },
    {
      id: "raw_codex_repo_prev",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      sourceId: "source_codex_repo",
      taskRunId: "run_codex_repo_20260610",
      recordType: "github_repo",
      sourceUrl: "https://github.com/openai/codex",
      contentHash: "54af72380f8400440ef2d335671e3307e7adf924df0f9cc43a7d6879f7a3db15",
      screenshotUrl: null,
      collectedAt: "2026-06-10T08:05:00.000Z",
      createdAt: "2026-06-10T08:05:00.000Z",
      content: {
        provider: "github",
        kind: "repo_snapshot",
        full_name: "openai/codex",
        stars: 100,
        forks: 19,
        open_issues: 5,
        default_branch: "main",
      },
    },
    {
      id: "raw_manual_product",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      taskRunId: "run_manual_json",
      recordType: "manual_json",
      sourceUrl: null,
      contentHash: "d0e3f73e35a02f5dff60f421b9b4f3ad7c4dd30f47c904aa344b63808e1929f6",
      screenshotUrl: null,
      collectedAt: "2026-06-11T08:00:00.000Z",
      createdAt: "2026-06-11T08:00:00.000Z",
      content: {
        provider: "manual_json",
        kind: "manual_payload",
        entity_type: "product",
        payload: {
          name: "Demo Product",
          price: 99,
          currency: "USD",
        },
      },
    },
    {
      id: "raw_manual_product_prev",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      taskRunId: "run_manual_json_prev",
      recordType: "manual_json",
      sourceUrl: null,
      contentHash: "1b9ab77f6a4d04d8c0ad01f73058e698d4a7e47fc0b42494b58da6418a01973f",
      screenshotUrl: null,
      collectedAt: "2026-06-10T08:00:00.000Z",
      createdAt: "2026-06-10T08:00:00.000Z",
      content: {
        provider: "manual_json",
        kind: "manual_payload",
        entity_type: "product",
        payload: {
          name: "Demo Product",
          price: 109,
          currency: "USD",
        },
      },
    },
  ];
}

export function getMockEntities(): Entity[] {
  return [
    {
      id: "entity_competitor_page",
      workspaceId: "workspace_mock",
      projectId: "project_competitor",
      entityType: "web_page",
      externalId: "https://example.com/pricing",
      canonicalUrl: "https://example.com/pricing",
      name: "Example Pricing Page",
      domain: "competitor",
      latestSnapshotId: "snapshot_new",
      firstSeenAt: "2026-06-10T07:20:00.000Z",
      lastSeenAt: "2026-06-11T07:20:00.000Z",
    },
    {
      id: "entity_codex_repo",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      entityType: "github_repo",
      externalId: "openai/codex",
      canonicalUrl: "https://github.com/openai/codex",
      name: "openai/codex",
      domain: "osint",
      latestSnapshotId: "snapshot_codex_repo",
      firstSeenAt: "2026-06-10T08:05:00.000Z",
      lastSeenAt: "2026-06-11T08:05:00.000Z",
    },
    {
      id: "entity_demo_product",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      entityType: "product",
      externalId: "Demo Product",
      canonicalUrl: null,
      name: "Demo Product",
      domain: "osint",
      latestSnapshotId: "snapshot_demo_product",
      firstSeenAt: "2026-06-11T08:00:00.000Z",
      lastSeenAt: "2026-06-11T08:00:00.000Z",
    },
  ];
}

export function getMockEntitySnapshots(entityId: string): EntitySnapshot[] {
  if (entityId === "entity_competitor_page") {
    return [
      {
        id: "snapshot_new",
        entityId,
        rawRecordId: "raw_competitor_page",
        capturedAt: "2026-06-11T07:20:00.000Z",
        createdAt: "2026-06-11T07:20:00.000Z",
        metrics: {
          content_hash: "new",
          text_length: 1490,
          changed_sections: 3,
        },
        snapshotData: {
          headline: "New annual plan",
          pricing: "Team plan changed",
          url: "https://example.com/pricing",
        },
      },
      {
        id: "snapshot_old",
        entityId,
        rawRecordId: "raw_competitor_page_old",
        capturedAt: "2026-06-10T07:20:00.000Z",
        createdAt: "2026-06-10T07:20:00.000Z",
        metrics: {
          content_hash: "old",
          text_length: 1080,
          changed_sections: 0,
        },
        snapshotData: {
          headline: "Team plan",
          pricing: "Monthly only",
          url: "https://example.com/pricing",
        },
      },
    ];
  }
  if (entityId === "entity_codex_repo") {
    return [
      {
        id: "snapshot_codex_repo",
        entityId,
        rawRecordId: "raw_codex_repo",
        capturedAt: "2026-06-11T08:05:00.000Z",
        createdAt: "2026-06-11T08:05:00.000Z",
        metrics: {
          stars: 260,
          forks: 42,
          open_issues: 8,
        },
        snapshotData: {
          full_name: "openai/codex",
          stars: 260,
          forks: 42,
          default_branch: "main",
        },
      },
      {
        id: "snapshot_codex_repo_prev",
        entityId,
        rawRecordId: "raw_codex_repo_prev",
        capturedAt: "2026-06-10T08:05:00.000Z",
        createdAt: "2026-06-10T08:05:00.000Z",
        metrics: {
          stars: 100,
          forks: 19,
          open_issues: 5,
        },
        snapshotData: {
          full_name: "openai/codex",
          stars: 100,
          forks: 19,
          default_branch: "main",
        },
      },
    ];
  }
  return [
    {
      id: "snapshot_demo_product",
      entityId,
      rawRecordId: "raw_manual_product",
      capturedAt: "2026-06-11T08:00:00.000Z",
      createdAt: "2026-06-11T08:00:00.000Z",
      metrics: {
        price: 99,
      },
      snapshotData: {
        name: "Demo Product",
        price: 99,
        currency: "USD",
      },
    },
    {
      id: "snapshot_demo_product_prev",
      entityId,
      rawRecordId: "raw_manual_product_prev",
      capturedAt: "2026-06-10T08:00:00.000Z",
      createdAt: "2026-06-10T08:00:00.000Z",
      metrics: {
        price: 109,
      },
      snapshotData: {
        name: "Demo Product",
        price: 109,
        currency: "USD",
      },
    },
  ];
}

export function getMockSignals(): Signal[] {
  return [
    ...mockDriftSignals,
    {
      id: "signal_star_growth",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      entityId: "entity_codex_repo",
      signalType: "star_growth",
      previousSnapshotId: "snapshot_codex_repo_prev",
      currentSnapshotId: "snapshot_codex_repo",
      previousValue: 100,
      currentValue: 260,
      delta: 160,
      deltaRatio: 1.6,
      confidence: 90,
      severity: "medium",
      detectedAt: "2026-06-11T08:05:00.000Z",
      metadata: {
        metric: "stars",
      },
    },
    {
      id: "signal_page_changed",
      workspaceId: "workspace_mock",
      projectId: "project_competitor",
      entityId: "entity_competitor_page",
      signalType: "page_changed",
      previousSnapshotId: "snapshot_old",
      currentSnapshotId: "snapshot_new",
      previousValue: null,
      currentValue: 0.38,
      delta: null,
      deltaRatio: 0.38,
      confidence: 85,
      severity: "high",
      detectedAt: "2026-06-11T07:20:00.000Z",
      metadata: {
        previous_content_hash: "old",
        current_content_hash: "new",
      },
    },
    {
      id: "signal_data_quality_anomaly",
      workspaceId: "workspace_mock",
      projectId: "project_competitor",
      entityId: "entity_competitor_page",
      signalType: "data_quality_anomaly",
      previousSnapshotId: "snapshot_old",
      currentSnapshotId: "snapshot_new",
      previousValue: 0,
      currentValue: 3,
      delta: 3,
      deltaRatio: null,
      confidence: 72,
      severity: "medium",
      detectedAt: "2026-06-11T07:22:00.000Z",
      metadata: {
        failed_runs_24h: 3,
        latest_error: "HTTP 429 Too Many Requests",
        affected_source_id: "source_competitor_homepage",
      },
    },
  ];
}

export function getMockIntelligence(): IntelligenceItem[] {
  return [
    {
      id: "intel_star_growth",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      title: "openai/codex is showing accelerated traction",
      summary:
        "star_growth metric=stars was detected with severity=medium. delta=160, delta_ratio=1.6, final_score=87.70. The conclusion is backed by 3 evidence records.",
      intelligenceType: "trend",
      status: "new",
      impactScore: 96,
      confidenceScore: 90,
      noveltyScore: 100,
      urgencyScore: 58,
      finalScore: 87.7,
      generatedBy: "hybrid",
      domain: "osint",
      evidenceCount: 3,
      createdAt: "2026-06-11T08:06:00.000Z",
      updatedAt: "2026-06-11T08:06:00.000Z",
    },
    {
      id: "intel_page_changed",
      workspaceId: "workspace_mock",
      projectId: "project_competitor",
      title: "Competitor pricing page changed materially",
      summary:
        "page_changed was detected with severity=high. The change is concentrated in pricing and product navigation content.",
      intelligenceType: "risk",
      status: "reviewed",
      impactScore: 75,
      confidenceScore: 85,
      noveltyScore: 100,
      urgencyScore: 79,
      finalScore: 83.3,
      generatedBy: "hybrid",
      domain: "competitor",
      evidenceCount: 2,
      createdAt: "2026-06-11T07:20:00.000Z",
      updatedAt: "2026-06-11T07:40:00.000Z",
    },
  ];
}

export function getMockEvidences(intelligenceId: string): Evidence[] {
  if (intelligenceId === "intel_page_changed") {
    return [
      withEvidenceTrace({
        id: "evidence_page_signal",
        intelligenceId,
        signalId: "signal_page_changed",
        entityId: "entity_competitor_page",
        rawRecordId: "raw_competitor_page",
        evidenceType: "signal",
        title: "Signal page_changed",
        url: "https://example.com/pricing",
        excerpt: "page_changed: delta_ratio=0.38, severity=high.",
        highlightedText: "previous_snapshot=snapshot_old; current_snapshot=snapshot_new",
        screenshotUrl: "https://dummyimage.com/900x520/e5e7eb/111827&text=Pricing+Snapshot",
        createdAt: "2026-06-11T07:20:00.000Z",
      }),
      withEvidenceTrace({
        id: "evidence_page_raw",
        intelligenceId,
        signalId: "signal_page_changed",
        entityId: "entity_competitor_page",
        rawRecordId: "raw_competitor_page",
        evidenceType: "raw_record",
        title: "Raw record generic_web",
        url: "https://example.com/pricing",
        excerpt: '{"headline":"New annual plan","pricing":"Team plan changed"}',
        highlightedText: '{"headline":"New annual plan","pricing":"Team plan changed"}',
        screenshotUrl: "https://dummyimage.com/900x520/e5e7eb/111827&text=Pricing+Snapshot",
        createdAt: "2026-06-11T07:20:01.000Z",
      }),
    ];
  }
  return [
    withEvidenceTrace({
      id: "evidence_signal_star",
      intelligenceId,
      signalId: "signal_star_growth",
      entityId: "entity_codex_repo",
      rawRecordId: "raw_codex_repo",
      evidenceType: "signal",
      title: "Signal star_growth",
      url: null,
      excerpt: "star_growth on stars: previous=100, current=260, delta=160, severity=medium.",
      highlightedText:
        "confidence=90; delta_ratio=1.6; previous_snapshot=snapshot_codex_repo_prev; current_snapshot=snapshot_codex_repo",
      screenshotUrl: null,
      createdAt: "2026-06-11T08:05:00.000Z",
    }),
    withEvidenceTrace({
      id: "evidence_snapshot_star",
      intelligenceId,
      signalId: "signal_star_growth",
      entityId: "entity_codex_repo",
      rawRecordId: "raw_codex_repo",
      evidenceType: "snapshot",
      title: "Current entity snapshot",
      url: null,
      excerpt: 'snapshot=snapshot_codex_repo; metrics={"stars":260}',
      highlightedText: '{"stars":260}',
      screenshotUrl: null,
      createdAt: "2026-06-11T08:05:01.000Z",
    }),
    withEvidenceTrace({
      id: "evidence_raw_star",
      intelligenceId,
      signalId: "signal_star_growth",
      entityId: "entity_codex_repo",
      rawRecordId: "raw_codex_repo",
      evidenceType: "raw_record",
      title: "Raw record github_repo",
      url: "https://github.com/openai/codex",
      excerpt: '{"full_name":"openai/codex","stars":260}',
      highlightedText: '{"full_name":"openai/codex","stars":260}',
      screenshotUrl: null,
      createdAt: "2026-06-11T08:05:02.000Z",
    }),
  ];
}

function withEvidenceTrace(
  evidence: Omit<
    Evidence,
    "entity" | "rawRecord" | "referenceMetadata" | "signal" | "source" | "taskRun"
  >,
): Evidence {
  const signal = getMockSignals().find((item) => item.id === evidence.signalId) ?? null;
  const entity = getMockEntities().find((item) => item.id === evidence.entityId) ?? null;
  const rawRecord = getMockRawRecords().find((item) => item.id === evidence.rawRecordId) ?? null;
  const source = getMockSources().find((item) => item.id === rawRecord?.sourceId) ?? null;
  const task = getMockTasks().find((item) => item.sourceId === rawRecord?.sourceId) ?? null;
  return {
    ...evidence,
    referenceMetadata: {
      claim_type: evidence.evidenceType,
      json_paths: evidence.rawRecordId ? ["$.content"] : ["$.signal"],
      source_layer: evidence.rawRecordId ? "raw_record" : "signal",
    },
    signal: signal
      ? {
          id: signal.id,
          signalType: signal.signalType,
          severity: signal.severity,
          previousSnapshotId: signal.previousSnapshotId,
          currentSnapshotId: signal.currentSnapshotId,
          currentValue: signal.currentValue,
          previousValue: signal.previousValue,
          delta: signal.delta,
          deltaRatio: signal.deltaRatio,
          confidence: signal.confidence,
          metadata: signal.metadata,
          detectedAt: signal.detectedAt,
        }
      : null,
    entity: entity
      ? {
          id: entity.id,
          entityType: entity.entityType,
          externalId: entity.externalId,
          canonicalUrl: entity.canonicalUrl,
          name: entity.name,
          domain: entity.domain,
          latestSnapshotId: entity.latestSnapshotId,
        }
      : null,
    rawRecord: rawRecord
      ? {
          id: rawRecord.id,
          sourceId: rawRecord.sourceId,
          taskRunId: rawRecord.taskRunId,
          recordType: rawRecord.recordType,
          sourceUrl: rawRecord.sourceUrl,
          contentHash: rawRecord.contentHash,
          screenshotUrl: rawRecord.screenshotUrl,
          contentPreview: rawRecord.content,
          collectedAt: rawRecord.collectedAt,
          createdAt: rawRecord.createdAt,
        }
      : null,
    taskRun: rawRecord
      ? {
          id: rawRecord.taskRunId,
          taskId: task?.id ?? "task_unknown",
          status: "success",
          startedAt: rawRecord.collectedAt,
          finishedAt: rawRecord.createdAt,
          recordsCount: 1,
          entitiesCount: 1,
          errorMessage: null,
        }
      : null,
    source: source
      ? {
          id: source.id,
          name: source.name,
          type: source.type,
          url: source.url,
          enabled: source.enabled,
        }
      : null,
  };
}

export function getMockReports(): Report[] {
  const intelligence = getMockIntelligence();
  const content = [
    "# AI Scrapy Tools 日报 — 2026-06-11",
    "",
    "## 监控概览",
    `- 新增情报数：${intelligence.length}`,
    "",
    "## 核心发现",
    "",
    "### osint",
    `1. **${intelligence[0].title}** — Score: ${intelligence[0].finalScore}`,
    `   ${intelligence[0].summary}`,
    `   情报 ID：${intelligence[0].id}`,
    `   证据数：${intelligence[0].evidenceCount}`,
    "",
    "### competitor",
    `1. **${intelligence[1].title}** — Score: ${intelligence[1].finalScore}`,
    `   ${intelligence[1].summary}`,
    `   情报 ID：${intelligence[1].id}`,
    `   证据数：${intelligence[1].evidenceCount}`,
  ].join("\n");
  return [
    {
      id: "report_daily_20260611",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      reportType: "daily",
      title: "AI Scrapy Tools 日报 — 2026-06-11",
      content,
      status: "generated",
      periodStart: "2026-06-11T00:00:00.000Z",
      periodEnd: "2026-06-11T08:30:00.000Z",
      createdAt: "2026-06-11T08:30:00.000Z",
    },
  ];
}

const mockReportAuditEvents: ReportAuditEvent[] = [
  {
    id: "audit_report_generated",
    workspaceId: "workspace_mock",
    reportId: "report_daily_20260611",
    actorId: "user_mock",
    eventType: "generated",
    fromStatus: null,
    toStatus: "generated",
    metadata: { project_id: "project_osint" },
    createdAt: "2026-06-11T08:30:00.000Z",
  },
];

const mockReportSubscriptions: ReportSubscription[] = [
  {
    id: "subscription_daily_osint",
    workspaceId: "workspace_mock",
    userId: "user_mock",
    projectId: "project_osint",
    reportType: "daily",
    scheduleTime: "09:00",
    timezone: "Asia/Shanghai",
    channels: ["in_app", "email"],
    enabled: true,
    nextRunAt: nextMockRunAt("09:00", "Asia/Shanghai"),
    lastSentAt: null,
    latestRun: null,
    createdAt: "2026-06-11T08:00:00.000Z",
    updatedAt: "2026-06-11T08:00:00.000Z",
  },
];

const mockReportSubscriptionRuns: ReportSubscriptionRun[] = [];

export function createMockGeneratedReport(input: ReportGenerateInput): Report {
  const base = getMockReports()[0];
  const project = input.projectId
    ? getMockProjects().find((item) => item.id === input.projectId)
    : null;
  const periodEnd = input.periodEnd ?? new Date().toISOString();
  const periodStart = input.periodStart ?? base.periodStart;
  const titlePrefix = project?.name ?? "全局";
  const report = {
    ...base,
    id: `report_daily_${Date.now()}`,
    projectId: input.projectId ?? null,
    status: "generated",
    title: `${titlePrefix} 日报 — ${new Date(periodEnd).toISOString().slice(0, 10)}`,
    periodEnd,
    periodStart,
    createdAt: new Date().toISOString(),
  };
  mockReportAuditEvents.push({
    id: `audit_${report.id}_generated`,
    workspaceId: report.workspaceId,
    reportId: report.id,
    actorId: "user_mock",
    eventType: "generated",
    fromStatus: null,
    toStatus: "generated",
    metadata: { project_id: report.projectId ?? "global" },
    createdAt: report.createdAt,
  });
  return report;
}

export function getMockReportEvidenceReferences(reportId: string): ReportEvidenceReference[] {
  const report = getMockReports().find((item) => item.id === reportId);
  if (!report) {
    return [];
  }
  const intelligenceIds = new Set(
    [...report.content.matchAll(/(?:情报 ID：|intelligence_id=)([a-zA-Z0-9_-]+)/g)].map(
      (match) => match[1],
    ),
  );
  return getMockIntelligence()
    .filter((intelligence) => intelligenceIds.has(intelligence.id))
    .map((intelligence) => ({
      intelligence,
      evidences: getMockEvidences(intelligence.id),
    }));
}

export function getMockReportAuditEvents(reportId: string): ReportAuditEvent[] {
  return mockReportAuditEvents
    .filter((event) => event.reportId === reportId)
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt));
}

export function createMockReportAuditEvent(
  reportId: string,
  eventType: "share_link_copied" | "share_sheet_opened" | "sent",
  metadata: Record<string, string> = {},
): ReportAuditEvent {
  const report = getMockReports().find((item) => item.id === reportId);
  const event: ReportAuditEvent = {
    id: `audit_${reportId}_${eventType}_${Date.now()}`,
    workspaceId: report?.workspaceId ?? "workspace_mock",
    reportId,
    actorId: "user_mock",
    eventType,
    fromStatus: report?.status ?? null,
    toStatus: eventType === "sent" ? "sent" : (report?.status ?? null),
    metadata,
    createdAt: new Date().toISOString(),
  };
  mockReportAuditEvents.push(event);
  return event;
}

export function getMockReportSubscriptions(): ReportSubscription[] {
  return [...mockReportSubscriptions].sort((left, right) => {
    if (left.enabled !== right.enabled) {
      return left.enabled ? -1 : 1;
    }
    return right.createdAt.localeCompare(left.createdAt);
  });
}

export function getMockReportSubscriptionRuns(subscriptionId: string): ReportSubscriptionRun[] {
  return mockReportSubscriptionRuns
    .filter((run) => run.subscriptionId === subscriptionId)
    .sort((left, right) => right.startedAt.localeCompare(left.startedAt));
}

export function upsertMockReportSubscription(
  input: ReportSubscriptionInput,
): ReportSubscription {
  const now = new Date().toISOString();
  const projectId = input.projectId ?? null;
  const reportType = input.reportType ?? "daily";
  const existing = mockReportSubscriptions.find(
    (item) => item.projectId === projectId && item.reportType === reportType,
  );
  if (existing) {
    existing.scheduleTime = input.scheduleTime;
    existing.timezone = input.timezone;
    existing.channels = input.channels;
    existing.enabled = input.enabled;
    existing.nextRunAt = input.enabled ? nextMockRunAt(input.scheduleTime, input.timezone) : null;
    existing.updatedAt = now;
    return existing;
  }

  const subscription: ReportSubscription = {
    id: `subscription_${Date.now()}`,
    workspaceId: "workspace_mock",
    userId: "user_mock",
    projectId,
    reportType,
    scheduleTime: input.scheduleTime,
    timezone: input.timezone,
    channels: input.channels,
    enabled: input.enabled,
    nextRunAt: input.enabled ? nextMockRunAt(input.scheduleTime, input.timezone) : null,
    lastSentAt: null,
    latestRun: null,
    createdAt: now,
    updatedAt: now,
  };
  mockReportSubscriptions.push(subscription);
  return subscription;
}

export function runMockReportSubscription(subscriptionId: string): ReportSubscription {
  const subscription = mockReportSubscriptions.find((item) => item.id === subscriptionId);
  if (!subscription) {
    throw new Error("Report subscription not found");
  }
  return executeMockReportSubscription(subscription, "manual");
}

export function retryMockReportSubscriptionRun(
  subscriptionId: string,
  runId: string,
): ReportSubscription {
  const subscription = mockReportSubscriptions.find((item) => item.id === subscriptionId);
  if (!subscription) {
    throw new Error("Report subscription not found");
  }
  const run = mockReportSubscriptionRuns.find(
    (item) => item.subscriptionId === subscriptionId && item.id === runId,
  );
  if (!run) {
    throw new Error("Report subscription run not found");
  }
  if (run.status !== "failed" && run.status !== "partial_success") {
    throw new Error("Only failed or partially successful report subscription runs can be retried");
  }
  const retryChannels = Object.keys(run.skippedChannels) as ReportDeliveryChannel[];
  return executeMockReportSubscription(
    subscription,
    "retry",
    retryChannels.length > 0 ? retryChannels : subscription.channels,
    run.reportId ?? "report_daily_20260611",
  );
}

function executeMockReportSubscription(
  subscription: ReportSubscription,
  triggerType: "manual" | "retry",
  channels: ReportDeliveryChannel[] = subscription.channels,
  reportId = "report_daily_20260611",
): ReportSubscription {
  const now = new Date().toISOString();
  const deliveredChannels = channels.includes("in_app") ? ["in_app" as const] : [];
  const skippedChannels: Record<string, string> = channels.includes("email")
    ? { email: "smtp_not_configured" }
    : {};
  const status =
    deliveredChannels.length > 0 && Object.keys(skippedChannels).length > 0
      ? "partial_success"
      : deliveredChannels.length > 0
        ? "success"
        : "failed";
  if (deliveredChannels.length > 0) {
    subscription.lastSentAt = now;
  }
  subscription.nextRunAt = subscription.enabled
    ? nextMockRunAt(subscription.scheduleTime, subscription.timezone)
    : null;
  const run: ReportSubscriptionRun = {
    id: `subscription_run_${Date.now()}_${mockReportSubscriptionRuns.length}`,
    workspaceId: subscription.workspaceId,
    subscriptionId: subscription.id,
    reportId,
    triggerType,
    status,
    deliveredChannels,
    skippedChannels,
    errorMessage:
      status === "success"
        ? null
        : Object.keys(skippedChannels).length > 0
          ? "email: smtp_not_configured"
          : "No delivery channel completed.",
    startedAt: now,
    finishedAt: now,
  };
  mockReportSubscriptionRuns.push(run);
  subscription.latestRun = run;
  subscription.updatedAt = now;
  return subscription;
}

function nextMockRunAt(scheduleTime: string, timezone: string) {
  const [hourText, minuteText] = scheduleTime.split(":");
  const now = new Date();
  const next = new Date(now);
  next.setHours(Number(hourText), Number(minuteText), 0, 0);
  if (next <= now) {
    next.setDate(next.getDate() + 1);
  }
  if (timezone === "UTC") {
    return new Date(Date.UTC(next.getFullYear(), next.getMonth(), next.getDate(), Number(hourText), Number(minuteText))).toISOString();
  }
  return next.toISOString();
}

export function getMockAlertRules(): AlertRule[] {
  return [
    ...mockDriftAlertRules,
    {
      id: "rule_high_severity",
      workspaceId: "workspace_mock",
      projectId: null,
      name: "High severity signal",
      signalType: "*",
      condition: { field: "severity", op: "in", value: ["high", "critical"] },
      channel: "in_app",
      enabled: true,
      createdAt: "2026-06-11T07:00:00.000Z",
    },
    {
      id: "rule_data_quality",
      workspaceId: "workspace_mock",
      projectId: "project_competitor",
      name: "Data quality anomaly watch",
      signalType: "data_quality_anomaly",
      condition: { field: "severity", op: "in", value: ["medium", "high", "critical"] },
      channel: "both",
      enabled: true,
      createdAt: "2026-06-11T07:05:00.000Z",
    },
    {
      id: "rule_score_threshold",
      workspaceId: "workspace_mock",
      projectId: null,
      name: "Final score above 80",
      signalType: "*",
      condition: { field: "final_score", op: "gte", value: 80 },
      channel: "email",
      enabled: false,
      createdAt: "2026-06-11T07:10:00.000Z",
    },
  ];
}

export function getMockAlertEvents(): AlertEvent[] {
  return [
    ...mockDriftAlertEvents,
    {
      id: "event_page_changed",
      ruleId: "rule_high_severity",
      signalId: "signal_page_changed",
      status: "sent",
      payload: {
        rule_name: "High severity signal",
        signal_type: "page_changed",
        severity: "high",
        project_id: "project_competitor",
        intelligence_id: "intel_page_changed",
        domain: "competitor",
        final_score: 83.3,
        intelligence_type: "risk",
      },
      triggeredAt: "2026-06-11T07:21:00.000Z",
      sentAt: "2026-06-11T07:21:01.000Z",
    },
    {
      id: "event_data_quality",
      ruleId: "rule_data_quality",
      signalId: "signal_data_quality_anomaly",
      status: "triggered",
      payload: {
        rule_name: "Data quality anomaly watch",
        signal_type: "data_quality_anomaly",
        severity: "medium",
        project_id: "project_competitor",
        domain: "competitor",
        failed_runs_24h: 3,
        latest_error: "HTTP 429 Too Many Requests",
        channel: "both",
      },
      triggeredAt: "2026-06-11T07:22:00.000Z",
      sentAt: null,
    },
    {
      id: "event_star_growth",
      ruleId: "rule_score_threshold",
      signalId: "signal_star_growth",
      status: "acknowledged",
      payload: {
        rule_name: "Final score above 80",
        signal_type: "star_growth",
        severity: "medium",
        project_id: "project_osint",
        intelligence_id: "intel_star_growth",
        domain: "osint",
        final_score: 87.7,
        intelligence_type: "trend",
        channel: "email",
      },
      triggeredAt: "2026-06-11T08:06:30.000Z",
      sentAt: "2026-06-11T08:06:31.000Z",
    },
  ];
}

export function getMockNotifications(): NotificationItem[] {
  return [
    ...mockDriftNotifications,
    {
      id: "notification_alert_data_quality",
      userId: "user_mock",
      title: "预警触发：Data quality anomaly watch",
      body: "source_competitor_homepage 在 24 小时内出现 3 次失败，最近错误为 HTTP 429。",
      notificationType: "alert",
      referenceType: "alert_event",
      referenceId: "event_data_quality",
      isRead: false,
      createdAt: "2026-06-11T07:22:02.000Z",
    },
    {
      id: "notification_alert_page_changed",
      userId: "user_mock",
      title: "预警命中：High severity signal",
      body: "page_changed 命中 severity",
      notificationType: "alert",
      referenceType: "alert_event",
      referenceId: "event_page_changed",
      isRead: false,
      createdAt: "2026-06-11T07:21:01.000Z",
    },
    {
      id: "notification_task_failed_linkedin",
      userId: "user_mock",
      title: "采集任务失败：LinkedIn 公司动态",
      body: "task_linkedin_company 连续重试失败，已生成 data_quality_anomaly 信号并等待处理。",
      notificationType: "task_failed",
      referenceType: "task_run",
      referenceId: "run_linkedin_company_failed",
      isRead: false,
      createdAt: "2026-06-11T07:18:00.000Z",
    },
    {
      id: "notification_report_daily",
      userId: "user_mock",
      title: "日报已生成：AI Scrapy Tools 日报 — 2026-06-11",
      body: "报告已进入站内通知中心，可从报告中心查看完整内容。",
      notificationType: "report_ready",
      referenceType: "report",
      referenceId: "report_daily_20260611",
      isRead: true,
      createdAt: "2026-06-11T08:31:00.000Z",
    },
  ];
}

export function getMockEmailChannelStatus(): EmailChannelStatus {
  return {
    status: "not_configured",
    configured: false,
    missingSettings: ["SMTP_HOST", "SMTP_FROM"],
    hostConfigured: false,
    port: 587,
    senderConfigured: false,
    authConfigured: false,
    tlsMode: "starttls",
    reason: "smtp_not_configured",
  };
}

export function testMockEmailChannel(): EmailChannelTestResult {
  return {
    delivered: false,
    recipientEmail: "demo@example.com",
    status: getMockEmailChannelStatus(),
    reason: "smtp_not_configured",
    testedAt: new Date().toISOString(),
  };
}

export function getMockSignalSnapshotCompare(signalId: string): SignalSnapshotCompare {
  if (signalId === "signal_page_changed") {
    return {
      signalId,
      entityId: "entity_competitor_page",
      signalType: "page_changed",
      previousSnapshot: {
        id: "snapshot_old",
        rawRecordId: "raw_competitor_page_old",
        metrics: { content_hash: "old", text_length: 1080 },
        snapshotData: { headline: "Team plan", pricing: "Monthly only" },
        capturedAt: "2026-06-10T07:20:00.000Z",
        createdAt: "2026-06-10T07:20:00.000Z",
      },
      currentSnapshot: {
        id: "snapshot_new",
        rawRecordId: "raw_competitor_page",
        metrics: { content_hash: "new", text_length: 1490 },
        snapshotData: { headline: "New annual plan", pricing: "Team plan changed" },
        capturedAt: "2026-06-11T07:20:00.000Z",
        createdAt: "2026-06-11T07:20:00.000Z",
      },
      metricsDiff: [
        {
          metric: "content_hash",
          previousValue: "old",
          currentValue: "new",
          delta: null,
          deltaRatio: null,
        },
        {
          metric: "text_length",
          previousValue: 1080,
          currentValue: 1490,
          delta: 410,
          deltaRatio: 0.37962962962962965,
        },
      ],
    };
  }
  return {
    signalId,
    entityId: "entity_codex_repo",
    signalType: "star_growth",
    previousSnapshot: {
      id: "snapshot_codex_repo_prev",
      rawRecordId: "raw_codex_repo_prev",
      metrics: { stars: 100 },
      snapshotData: { full_name: "openai/codex", stars: 100 },
      capturedAt: "2026-06-10T08:05:00.000Z",
      createdAt: "2026-06-10T08:05:00.000Z",
    },
    currentSnapshot: {
      id: "snapshot_codex_repo",
      rawRecordId: "raw_codex_repo",
      metrics: { stars: 260 },
      snapshotData: { full_name: "openai/codex", stars: 260 },
      capturedAt: "2026-06-11T08:05:00.000Z",
      createdAt: "2026-06-11T08:05:00.000Z",
    },
    metricsDiff: [
      {
        metric: "stars",
        previousValue: 100,
        currentValue: 260,
        delta: 160,
        deltaRatio: 1.6,
      },
    ],
  };
}
