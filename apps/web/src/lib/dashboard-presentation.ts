import type { Route } from "next";

import type { DashboardSummary } from "@/types/dashboard";

export type DashboardAttentionItem = {
  detail: string;
  href: Route;
  id: string;
  kind: "active_alerts" | "failed_task" | "stale_task";
  nextAction: string;
  title: string;
};

export function buildDashboardAttentionItems(
  dashboard: DashboardSummary,
): DashboardAttentionItem[] {
  const staleTasks: DashboardAttentionItem[] = dashboard.freshness.staleTasks.map(
    (task) => ({
      detail: task.lastRunAt
        ? `已超过 ${task.freshnessTargetHours} 小时新鲜度目标，可能延迟新信号。`
        : "启用后尚未产生采集记录，当前范围没有可验证的新鲜度。",
      href: "/tasks",
      id: `stale:${task.taskId}`,
      kind: "stale_task",
      nextAction: "检查任务配置与最近运行",
      title: task.taskName,
    }),
  );
  const failedTasks: DashboardAttentionItem[] =
    dashboard.taskHealth.recentFailures.map((failure) => ({
      detail: failure.errorMessage
        ? `最近一次失败：${failure.errorMessage}`
        : "最近一次运行失败，但没有返回错误说明。",
      href: "/tasks",
      id: `failed:${failure.taskId}`,
      kind: "failed_task",
      nextAction: "查看失败记录并决定是否重试",
      title: failure.taskName,
    }));
  const alerts: DashboardAttentionItem[] =
    dashboard.activeAlerts > 0
      ? [
          {
            detail: `${dashboard.activeAlerts} 条预警仍处于活跃状态，需要人工确认影响。`,
            href: "/alerts",
            id: "active-alerts",
            kind: "active_alerts",
            nextAction: "进入预警队列逐条处理",
            title: "活跃预警待确认",
          },
        ]
      : [];

  return [...staleTasks, ...failedTasks, ...alerts];
}
