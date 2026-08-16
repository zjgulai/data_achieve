import { describe, expect, it } from "vitest";

import { getMockDashboard } from "@/lib/api/mock";
import { buildDashboardAttentionItems } from "@/lib/dashboard-presentation";
import type { DashboardSummary } from "@/types/dashboard";

function dashboardFixture(): DashboardSummary {
  return {
    intelligenceCount: 4,
    taskSuccessRate: 80,
    fieldCompleteness: 90,
    activeAlerts: 2,
    failedTasks: 1,
    recentRuns: 3,
    sourceCount: 2,
    typeBreakdown: [],
    domainBreakdown: [],
    topIntelligence: [],
    taskHealth: {
      totalTasks: 2,
      enabledTasks: 2,
      failedTasks: 1,
      recentRuns: 3,
      recentFailures: [
        {
          taskId: "failed-task",
          taskName: "失败采集",
          status: "failed",
          errorMessage: "timeout",
          createdAt: "2026-07-22T08:00:00Z",
        },
      ],
    },
    freshness: {
      generatedAt: "2026-07-22T09:00:00Z",
      latestCollectionAt: "2026-07-22T08:30:00Z",
      staleEnabledTasks: 1,
      staleTasks: [
        {
          taskId: "stale-task",
          taskName: "过期采集",
          collectorType: "public_feed",
          status: "enabled",
          lastRunAt: "2026-07-21T08:00:00Z",
          freshnessTargetHours: 4,
          staleHours: 20,
        },
      ],
    },
  };
}

describe("dashboard presentation", () => {
  it("turns exceptions into explicit owner actions", () => {
    const items = buildDashboardAttentionItems(dashboardFixture());

    expect(items.map((item) => item.kind)).toEqual([
      "stale_task",
      "failed_task",
      "active_alerts",
    ]);
    expect(items.map((item) => item.href)).toEqual([
      "/tasks",
      "/tasks",
      "/alerts",
    ]);
    expect(items.every((item) => item.nextAction.length > 0)).toBe(true);
  });

  it("keeps mock dashboard data inside the selected project", () => {
    const allProjects = getMockDashboard();
    const osintProject = getMockDashboard(undefined, "project_osint");
    const emptyProject = getMockDashboard(
      undefined,
      "project_marketplace_price",
    );

    expect(allProjects.intelligenceCount).toBe(2);
    expect(osintProject.intelligenceCount).toBe(1);
    expect(osintProject.topIntelligence).toHaveLength(1);
    expect(osintProject.topIntelligence[0]?.domain).toBe("osint");
    expect(osintProject.domainBreakdown.map((item) => item.domain)).toEqual([
      "osint",
    ]);
    expect(emptyProject.intelligenceCount).toBe(0);
    expect(emptyProject.domainBreakdown.map((item) => item.domain)).toEqual([
      "ecommerce",
    ]);
  });
});
