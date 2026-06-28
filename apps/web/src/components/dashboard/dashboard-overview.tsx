"use client";

import {
  AlertTriangle,
  ArrowRight,
  Bell,
  BookOpenCheck,
  ChartNoAxesCombined,
  CheckCircle2,
  Database,
  FileText,
  Gauge,
  RadioTower,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getDashboardOverview } from "@/lib/api/dashboard";
import { useTrainingOverview } from "@/lib/use-training-overview";
import {
  WorkbenchDomainCard,
  WorkbenchDistributionRow,
  WorkbenchMetric,
  WorkbenchPanel,
  WorkbenchStatusRow,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import type { DashboardSummary } from "@/types/dashboard";
import type { ToolkitOverview } from "@/types/toolkit";

const domainLabels: Record<string, string> = {
  competitor: "竞品守望",
  ecommerce: "电商风向",
  osint: "开源雷达",
  social: "社媒脉搏",
  agent: "Agent 生态",
  platform: "平台采集",
  governance: "合规边界",
};

const domainDescriptions: Record<string, string> = {
  competitor: "页面快照、策略变化、品牌动作",
  ecommerce: "价格排名、商品信号、渠道趋势",
  osint: "GitHub 趋势、开源项目、技术信号",
  social: "内容热度、用户讨论、导入信号",
  agent: "AI Agent、Skills、MCP、采集编排工具",
  platform: "平台公开数据、方法边界、采集入口",
  governance: "授权、频控、禁止项、风险边界",
};

export function DashboardOverview({ domain }: { domain?: string }) {
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const trainingOverview = useTrainingOverview();

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    getDashboardOverview({ domain, limit: 10 })
      .then((response) => {
        if (mounted) {
          setDashboard(response);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "仪表盘数据暂不可用");
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [domain]);

  const context = useMemo(() => {
    const title = domain ? `${domainLabels[domain] ?? domain} 洞察工作台` : "市场洞察工作台";
    const description = domain
      ? domainDescriptions[domain] ?? "域内情报、任务健康、数据质量"
      : "跨域情报、任务健康、数据质量";
    return { description, title };
  }, [domain]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error || !dashboard) {
    return (
      <div className="rounded-2xl border border-[#FFD7DF] bg-[#FFF7F8] px-4 py-3 text-sm text-[#C25B6E]">
        {error ?? "仪表盘数据暂不可用"}
      </div>
    );
  }

  const primaryIntelligence = dashboard.topIntelligence[0] ?? null;
  const latestCollectionLabel = dashboard.freshness.latestCollectionAt
    ? `最近采集 ${formatRelativeTime(dashboard.freshness.latestCollectionAt)}`
    : "尚无采集记录";

  return (
    <div className="grid min-w-0 grid-cols-1 gap-5">
      <section className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <WorkbenchTag tone="rose">实时概览</WorkbenchTag>
              <WorkbenchTag tone="neutral">生成 {formatDateTime(dashboard.freshness.generatedAt)}</WorkbenchTag>
              <WorkbenchTag tone={dashboard.freshness.latestCollectionAt ? "green" : "red"}>
                {latestCollectionLabel}
              </WorkbenchTag>
              <WorkbenchTag tone={dashboard.freshness.staleEnabledTasks > 0 ? "red" : "green"}>
                {dashboard.freshness.staleEnabledTasks > 0
                  ? `${dashboard.freshness.staleEnabledTasks} 个启用任务过期`
                  : "启用任务新鲜度正常"}
              </WorkbenchTag>
              <WorkbenchTag tone={dashboard.activeAlerts > 0 ? "red" : "green"}>
                {dashboard.activeAlerts > 0 ? `${dashboard.activeAlerts} 条活跃预警` : "暂无活跃预警"}
              </WorkbenchTag>
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-[#1D1D1F]">{context.title}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#86868B]">{context.description}</p>
          </div>
          {primaryIntelligence ? (
            <Link
              className="group rounded-2xl border border-[#F4D9DF] bg-[#FFF7F8] p-4 transition-colors hover:border-[#C25B6E]"
              href={`/intelligence/${primaryIntelligence.id}`}
            >
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#FCEBF0] text-[#C25B6E]">
                  <Sparkles size={18} aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-[#C25B6E]">最高优先级情报</p>
                  <p className="mt-1 line-clamp-2 text-sm font-semibold text-[#1D1D1F]">
                    {primaryIntelligence.title}
                  </p>
                  <p className="mt-2 text-xs font-medium text-[#9E6A76]">
                    更新 {formatRelativeTime(primaryIntelligence.updatedAt)}
                  </p>
                  <span className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[#C25B6E]">
                    查看详情
                    <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                  </span>
                </div>
              </div>
            </Link>
          ) : null}
        </div>
      </section>

      <TrainingOverviewPanel
        error={trainingOverview.error}
        loading={trainingOverview.loading}
        overview={trainingOverview.overview}
      />

      <section className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <WorkbenchMetric
          caption={latestCollectionLabel}
          icon={RadioTower}
          label="情报总量"
          tone="rose"
          value={String(dashboard.intelligenceCount)}
        />
        <WorkbenchMetric
          caption="采集链路"
          icon={CheckCircle2}
          label="任务成功率"
          tone="green"
          value={`${formatNumber(dashboard.taskSuccessRate)}%`}
        />
        <WorkbenchMetric
          caption="结构化字段"
          icon={Database}
          label="字段完整率"
          tone="violet"
          value={`${formatNumber(dashboard.fieldCompleteness)}%`}
        />
        <WorkbenchMetric
          caption={`${dashboard.sourceCount} sources`}
          icon={Bell}
          label="活跃预警"
          tone={dashboard.activeAlerts > 0 ? "red" : "amber"}
          value={String(dashboard.activeAlerts)}
        />
        <WorkbenchMetric
          caption={`${dashboard.taskHealth.enabledTasks} enabled`}
          icon={AlertTriangle}
          label="失败任务"
          tone={dashboard.failedTasks > 0 ? "red" : "green"}
          value={String(dashboard.failedTasks)}
        />
      </section>

      <section className="grid min-w-0 grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
        <WorkbenchPanel
          action={
            <Link className="text-xs font-semibold text-[#C25B6E]" href="/intelligence">
              查看全部
            </Link>
          }
          icon={FileText}
          label="情报"
          subtitle="按 final score 排序，优先处理有证据链的信号"
          title="Top Intelligence"
        >
          <div className="grid min-w-0 grid-cols-1 gap-3">
            {dashboard.topIntelligence.map((item, index) => (
              <Link
                className="group rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4 transition-colors hover:border-[#C25B6E] hover:bg-[#FFF7F8]"
                href={`/intelligence/${item.id}`}
                key={item.id}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-white text-xs font-semibold text-[#C25B6E]">
                        {index + 1}
                      </span>
                      <h3 className="line-clamp-1 text-sm font-semibold text-[#1D1D1F]">
                        {item.title}
                      </h3>
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-[#5F5757]">{item.summary}</p>
                  </div>
                  <span className="self-start rounded-xl bg-[#FCEBF0] px-3 py-1 text-sm font-semibold text-[#C25B6E]">
                    {item.finalScore}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-[#86868B]">
                  <WorkbenchTag>{domainLabels[item.domain] ?? item.domain}</WorkbenchTag>
                  <WorkbenchTag>{item.type}</WorkbenchTag>
                  <WorkbenchTag>{item.status}</WorkbenchTag>
                  <WorkbenchTag>{item.evidenceCount} evidence</WorkbenchTag>
                  <WorkbenchTag>更新 {formatRelativeTime(item.updatedAt)}</WorkbenchTag>
                </div>
              </Link>
            ))}
            {dashboard.topIntelligence.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-8 text-sm text-[#86868B]">
                暂无情报
              </div>
            ) : null}
          </div>
        </WorkbenchPanel>

        <div className="grid min-w-0 grid-cols-1 gap-5">
        <WorkbenchPanel icon={RadioTower} label="情报" subtitle="类型占比与当前情报结构" title="情报类型">
              <div className="grid min-w-0 grid-cols-1 gap-4">
              {dashboard.typeBreakdown.map((item) => (
                <WorkbenchDistributionRow
                  key={item.type}
                  label={item.type}
                  tone="rose"
                  value={`${item.count}`}
                  width={item.percent}
                />
              ))}
              {dashboard.typeBreakdown.length === 0 ? (
                <p className="text-sm text-[#86868B]">暂无类型分布</p>
              ) : null}
            </div>
          </WorkbenchPanel>

        <WorkbenchPanel icon={ShieldAlert} label="任务" subtitle="任务可用性与数据源覆盖" title="任务健康">
            <div className="grid min-w-0 grid-cols-1 gap-2 text-sm">
              <WorkbenchStatusRow label="任务总数" value={dashboard.taskHealth.totalTasks} />
              <WorkbenchStatusRow label="启用任务" value={dashboard.taskHealth.enabledTasks} />
              <WorkbenchStatusRow
                label="失败任务"
                tone={dashboard.taskHealth.failedTasks > 0 ? "red" : "green"}
                value={dashboard.taskHealth.failedTasks}
              />
              <WorkbenchStatusRow
                label="过期启用任务"
                tone={dashboard.freshness.staleEnabledTasks > 0 ? "red" : "green"}
                value={dashboard.freshness.staleEnabledTasks}
              />
              <WorkbenchStatusRow label="最近运行记录" value={dashboard.taskHealth.recentRuns} />
              <WorkbenchStatusRow label="数据源数量" value={dashboard.sourceCount} />
              <WorkbenchStatusRow label="最近采集" value={latestCollectionLabel} />
            </div>
            {dashboard.freshness.staleTasks.length > 0 ? (
              <div className="mt-4 grid min-w-0 grid-cols-1 gap-2">
                {dashboard.freshness.staleTasks.map((task) => (
                  <div className="rounded-xl border border-[#FFD7DF] bg-[#FFF7F8] p-3 text-xs" key={task.taskId}>
                    <p className="font-semibold text-[#C25B6E]">{task.taskName}</p>
                    <p className="mt-1 leading-5 text-[#7A3D49]">
                      {task.lastRunAt
                        ? `上次运行 ${formatRelativeTime(task.lastRunAt)}，过期 ${formatStaleHours(task.staleHours)}`
                        : "启用后尚未产生采集运行"}
                    </p>
                    <p className="mt-1 text-[#9E6A76]">
                      {task.collectorType} · 目标 {task.freshnessTargetHours}h
                    </p>
                  </div>
                ))}
              </div>
            ) : null}
            {dashboard.taskHealth.recentFailures.length > 0 ? (
              <div className="mt-4 grid min-w-0 grid-cols-1 gap-2">
                {dashboard.taskHealth.recentFailures.map((failure) => (
                  <div className="rounded-xl border border-[#FFD7DF] bg-[#FFF7F8] p-3 text-xs" key={failure.taskId}>
                    <p className="font-semibold text-[#C25B6E]">{failure.taskName}</p>
                    <p className="mt-1 leading-5 text-[#7A3D49]">{failure.errorMessage ?? "No error message"}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </WorkbenchPanel>
        </div>
      </section>

      <section className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <WorkbenchPanel
          icon={ChartNoAxesCombined}
          label="业务"
          subtitle="四域情报、信号与项目分布"
          title="业务域拆解"
        >
          <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
            {dashboard.domainBreakdown.map((item) => (
              <WorkbenchDomainCard
                intelligenceCount={item.intelligenceCount}
                key={item.domain}
                label={domainLabels[item.domain] ?? item.domain}
                projectCount={item.projectCount}
                signalCount={item.signalCount}
              />
            ))}
            {dashboard.domainBreakdown.length === 0 ? (
              <p className="text-sm text-[#86868B]">暂无域内数据</p>
            ) : null}
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel icon={Gauge} label="闭环" subtitle="从采集到报告的闭环状态" title="闭环进度">
          <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-4">
            <WorkbenchMetric
              label="采集"
              size="compact"
              tone="green"
              value={`${dashboard.taskHealth.enabledTasks} 个启用任务`}
            />
            <WorkbenchMetric
              label="信号"
              size="compact"
              tone="rose"
              value={`${dashboard.domainBreakdown.reduce((sum, item) => sum + item.signalCount, 0)} 条信号`}
            />
            <WorkbenchMetric
              label="情报"
              size="compact"
              tone="violet"
              value={`${dashboard.intelligenceCount} 条情报`}
            />
            <WorkbenchMetric
              label="报告"
              size="compact"
              tone="amber"
              value={`${dashboard.recentRuns} 次运行`}
            />
          </div>
        </WorkbenchPanel>
      </section>
    </div>
  );
}

function TrainingOverviewPanel({
  error,
  loading,
  overview,
}: {
  error: string | null;
  loading: boolean;
  overview: ToolkitOverview | null;
}) {
  const metrics = overview?.metrics;
  return (
    <section className="min-w-0 rounded-2xl border border-[#E9E5E2] bg-white p-5">
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
        <div className="min-w-0">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-[#FFF4DE] px-3 py-1 text-xs font-semibold text-[#8C6824]">
            <BookOpenCheck size={14} aria-hidden="true" />
            采集方法资产
          </div>
          <h2 className="text-base font-semibold text-[#1D1D1F]">数据采集工具与平台方法库</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[#5F5757]">
            汇总 AI 采集工具、Agent/Skill/MCP、爬虫框架、平台采集 SOP、合规边界和证据链，作为采集方案设计和复核的参考资产。
          </p>
          {error ? (
            <p className="mt-2 text-xs font-semibold text-[#C25B6E]">{error}</p>
          ) : null}
        </div>
        <div className="grid min-w-0 grid-cols-2 gap-2 sm:grid-cols-5 xl:min-w-[520px]">
          <WorkbenchMetric
            label="源"
            value={loading ? "..." : String(metrics?.sourceCount ?? 0)}
          />
          <WorkbenchMetric
            label="工具"
            value={loading ? "..." : String(metrics?.toolCount ?? 0)}
          />
          <WorkbenchMetric
            label="方法"
            value={loading ? "..." : String(metrics?.methodCount ?? 0)}
          />
          <WorkbenchMetric
            label="情报"
            value={loading ? "..." : String(metrics?.intelligenceCount ?? 0)}
          />
          <WorkbenchMetric
            label="证据"
            value={loading ? "..." : String(metrics?.evidenceCount ?? 0)}
          />
        </div>
      </div>
      <div className="mt-4 grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-4">
        <TrainingLink href="/toolkit" label="打开工具库" />
        <TrainingLink href="/sources" label="查看采集源" />
        <TrainingLink href="/raw-records" label="查看证据" />
        <TrainingLink href="/reports" label="查看报告" />
      </div>
    </section>
  );
}

function TrainingLink({ href, label }: { href: Route; label: string }) {
  return (
    <Link
      className="inline-flex h-10 items-center justify-center rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]"
      href={href}
    >
      {label}
    </Link>
  );
}

function DashboardSkeleton() {
  return (
    <div className="grid gap-5">
      <div className="h-32 animate-pulse rounded-2xl border border-[#E9E5E2] bg-white" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <div className="h-32 animate-pulse rounded-2xl border border-[#E9E5E2] bg-white" key={index} />
        ))}
      </div>
      <div className="h-96 animate-pulse rounded-2xl border border-[#E9E5E2] bg-white" />
    </div>
  );
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? value.toString() : value.toFixed(1);
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "无记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "时间无效";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatRelativeTime(value: string | null | undefined) {
  if (!value) {
    return "无记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "时间无效";
  }
  const diffMs = Math.max(Date.now() - date.getTime(), 0);
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) {
    return "刚刚";
  }
  if (minutes < 60) {
    return `${minutes} 分钟前`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} 小时前`;
  }
  return `${Math.floor(hours / 24)} 天前`;
}

function formatStaleHours(value: number | null) {
  if (value === null) {
    return "未计时";
  }
  if (value < 1) {
    return `${Math.round(value * 60)} 分钟`;
  }
  return `${formatNumber(value)} 小时`;
}
