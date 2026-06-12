import type { DashboardSummary } from "@/types/dashboard";
import type { Entity, EntitySnapshot } from "@/types/entity";
import type { Evidence, IntelligenceItem } from "@/types/intelligence";
import type { AlertEvent, AlertRule } from "@/types/alert";
import type { NotificationItem } from "@/types/notification";
import type { AuthSession, Project } from "@/types/project";
import type { RawRecord } from "@/types/raw-record";
import type { Report } from "@/types/report";
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
  return [
    {
      id: "task_manual_json",
      projectId: "project_osint",
      sourceId: "source_manual_json",
      collectorType: "manual_json",
      name: "Manual Product JSON",
      scheduleCron: "0 8 * * *",
      status: "enabled",
      successCount: 1,
      failureCount: 0,
      lastRunAt: "2026-06-11T08:00:00.000Z",
    },
  ];
}

export function getMockTaskRun(taskId: string): TaskRun {
  return {
    id: `run_${Date.now()}`,
    taskId,
    status: "success",
    startedAt: new Date().toISOString(),
    finishedAt: new Date().toISOString(),
    recordsCount: 1,
    entitiesCount: 1,
    errorMessage: null,
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
  ];
}

export function getMockEntities(): Entity[] {
  return [
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
  ];
}

export function getMockSignals(): Signal[] {
  return [
    {
      id: "signal_star_growth",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      entityId: "entity_demo_product",
      signalType: "star_growth",
      previousSnapshotId: "snapshot_prev",
      currentSnapshotId: "snapshot_demo_product",
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
  ];
}

export function getMockIntelligence(): IntelligenceItem[] {
  return [
    {
      id: "intel_star_growth",
      workspaceId: "workspace_mock",
      projectId: "project_osint",
      title: "example/repo is showing accelerated traction",
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
      {
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
      },
      {
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
      },
    ];
  }
  return [
    {
      id: "evidence_signal_star",
      intelligenceId,
      signalId: "signal_star_growth",
      entityId: "entity_demo_product",
      rawRecordId: "raw_manual_product",
      evidenceType: "signal",
      title: "Signal star_growth",
      url: null,
      excerpt: "star_growth on stars: previous=100, current=260, delta=160, severity=medium.",
      highlightedText:
        "confidence=90; delta_ratio=1.6; previous_snapshot=snapshot_prev; current_snapshot=snapshot_demo_product",
      screenshotUrl: null,
      createdAt: "2026-06-11T08:05:00.000Z",
    },
    {
      id: "evidence_snapshot_star",
      intelligenceId,
      signalId: "signal_star_growth",
      entityId: "entity_demo_product",
      rawRecordId: "raw_manual_product",
      evidenceType: "snapshot",
      title: "Current entity snapshot",
      url: null,
      excerpt: 'snapshot=snapshot_demo_product; metrics={"stars":260}',
      highlightedText: '{"stars":260}',
      screenshotUrl: null,
      createdAt: "2026-06-11T08:05:01.000Z",
    },
    {
      id: "evidence_raw_star",
      intelligenceId,
      signalId: "signal_star_growth",
      entityId: "entity_demo_product",
      rawRecordId: "raw_manual_product",
      evidenceType: "raw_record",
      title: "Raw record manual_json",
      url: null,
      excerpt: '{"payload":{"full_name":"example/repo","stars":260}}',
      highlightedText: '{"payload":{"full_name":"example/repo","stars":260}}',
      screenshotUrl: null,
      createdAt: "2026-06-11T08:05:02.000Z",
    },
  ];
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
  ];
}

export function getMockNotifications(): NotificationItem[] {
  return [
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
    entityId: "entity_demo_product",
    signalType: "star_growth",
    previousSnapshot: {
      id: "snapshot_prev",
      rawRecordId: "raw_manual_product_prev",
      metrics: { stars: 100 },
      snapshotData: { full_name: "example/repo", stars: 100 },
      capturedAt: "2026-06-10T08:00:00.000Z",
      createdAt: "2026-06-10T08:00:00.000Z",
    },
    currentSnapshot: {
      id: "snapshot_demo_product",
      rawRecordId: "raw_manual_product",
      metrics: { stars: 260 },
      snapshotData: { full_name: "example/repo", stars: 260 },
      capturedAt: "2026-06-11T08:00:00.000Z",
      createdAt: "2026-06-11T08:00:00.000Z",
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
