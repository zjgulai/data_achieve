import type { DashboardSummary } from "@/types/dashboard";
import type { Entity, EntitySnapshot } from "@/types/entity";
import type { Evidence, IntelligenceItem } from "@/types/intelligence";
import type { AlertEvent, AlertRule } from "@/types/alert";
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
import type { CollectionTask, Collector, Source, TaskRun } from "@/types/source-task";

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
    projectName: "AI Scrapy Tools",
    projectDomain: "osint",
    sourceName: task.name,
    sourceUrl: null,
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

function mockNextRunAt(lastRunAt: string | null, targetHours: number) {
  if (!lastRunAt) {
    return new Date().toISOString();
  }
  return new Date(new Date(lastRunAt).getTime() + targetHours * 60 * 60_000).toISOString();
}

export function getMockTaskRun(taskId: string): TaskRun {
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
