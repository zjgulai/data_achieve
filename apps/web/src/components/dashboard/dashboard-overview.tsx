"use client";

import {
  AlertTriangle,
  ArrowRight,
  Bell,
  BookOpenCheck,
  ChartNoAxesCombined,
  CheckCircle2,
  ChevronDown,
  CircleCheckBig,
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

import {
  WorkbenchDomainCard,
  WorkbenchDistributionRow,
  WorkbenchMetric,
  WorkbenchPanel,
  WorkbenchStatusRow,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import { useProjectSelection } from "@/components/layout/project-selection-provider";
import { getDashboardOverview } from "@/lib/api/dashboard";
import { buildDashboardAttentionItems } from "@/lib/dashboard-presentation";
import { useTrainingOverview } from "@/lib/use-training-overview";
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
  const {
    clearProjectFilterApplied,
    loading: projectSelectionLoading,
    markProjectFilterApplied,
    selectedProject,
    selectedProjectId,
  } = useProjectSelection();
  const trainingOverview = useTrainingOverview();

  useEffect(() => {
    if (projectSelectionLoading) {
      setLoading(true);
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);
    clearProjectFilterApplied();
    getDashboardOverview({
      domain,
      limit: 10,
      projectId: selectedProjectId ?? undefined,
    })
      .then((response) => {
        if (!mounted) {
          return;
        }
        setDashboard(response);
        if (selectedProjectId) {
          markProjectFilterApplied(selectedProjectId);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(
            caught instanceof Error ? caught.message : "仪表盘数据暂不可用",
          );
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
  }, [
    clearProjectFilterApplied,
    domain,
    markProjectFilterApplied,
    projectSelectionLoading,
    selectedProjectId,
  ]);

  const context = useMemo(() => {
    const title = domain
      ? `${domainLabels[domain] ?? domain} 洞察工作台`
      : "市场洞察工作台";
    const description = domain
      ? domainDescriptions[domain] ?? "域内情报、任务健康、数据质量"
      : "从监测任务进入异常处理，再回到可追溯的业务洞察。";
    return { description, title };
  }, [domain]);

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error || !dashboard) {
    return (
      <div className="rounded-[var(--radius-3)] border border-[var(--state-danger)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--state-danger)]">
        {error ?? "仪表盘数据暂不可用"}
      </div>
    );
  }

  const primaryIntelligence = dashboard.topIntelligence[0] ?? null;
  const attentionItems = buildDashboardAttentionItems(dashboard);
  const latestCollectionLabel = dashboard.freshness.latestCollectionAt
    ? formatRelativeTime(dashboard.freshness.latestCollectionAt)
    : "尚无采集记录";
  const scopeLabel = selectedProject?.name ?? "全部项目";

  return (
    <div className="grid min-w-0 grid-cols-1 gap-5">
      <section className="overflow-hidden rounded-[var(--radius-4)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
        <div className="border-b border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 sm:px-5">
          <div className="flex flex-wrap items-center gap-2">
            <WorkbenchTag tone="rose">当前范围 · {scopeLabel}</WorkbenchTag>
            <WorkbenchTag tone="neutral">
              更新 {formatDateTime(dashboard.freshness.generatedAt)}
            </WorkbenchTag>
            <WorkbenchTag
              tone={dashboard.freshness.latestCollectionAt ? "green" : "red"}
            >
              最近采集 · {latestCollectionLabel}
            </WorkbenchTag>
          </div>
        </div>
        <div className="grid gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_minmax(19rem,0.55fr)] xl:items-end">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--action-primary)]">
              Outcome summary
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--text-primary)]">
              {context.title}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
              {context.description}
            </p>
          </div>
          {primaryIntelligence ? (
            <Link
              className="group rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--accent-1-soft)] p-4 transition-colors duration-[var(--duration-base)] hover:border-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
              href={`/intelligence/${primaryIntelligence.id}`}
            >
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--surface-primary)] text-[var(--action-primary)]">
                  <Sparkles size={18} aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-[var(--action-primary)]">
                    当前优先洞察
                  </p>
                  <p className="mt-1 line-clamp-2 text-sm font-semibold text-[var(--text-primary)]">
                    {primaryIntelligence.title}
                  </p>
                  <span className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[var(--action-primary)]">
                    查看 Evidence
                    <ArrowRight
                      className="transition-transform duration-[var(--duration-base)] group-hover:translate-x-0.5"
                      size={14}
                      aria-hidden="true"
                    />
                  </span>
                </div>
              </div>
            </Link>
          ) : (
            <div className="rounded-[var(--radius-3)] border border-dashed border-[var(--border-strong)] bg-[var(--surface-secondary)] p-4 text-sm text-[var(--text-tertiary)]">
              当前范围尚未形成可展示的洞察。
            </div>
          )}
        </div>
      </section>

      <section
        aria-labelledby="dashboard-outcome-heading"
        className="grid min-w-0 gap-3"
        data-testid="dashboard-outcome-summary"
      >
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase text-[var(--action-primary)]">
              Current outcome
            </p>
            <h2
              className="mt-1 text-lg font-semibold text-[var(--text-primary)]"
              id="dashboard-outcome-heading"
            >
              当前结果
            </h2>
          </div>
          <p className="text-xs text-[var(--text-tertiary)]">范围：{scopeLabel}</p>
        </div>
        <div className="grid min-w-0 grid-cols-2 gap-3 xl:grid-cols-4">
          <WorkbenchMetric
            caption="可进入审阅与交付"
            icon={FileText}
            label="已形成情报"
            size="large"
            tone="rose"
            value={String(dashboard.intelligenceCount)}
          />
          <WorkbenchMetric
            caption="异常、失败与过期"
            icon={ShieldAlert}
            label="待处理项"
            size="large"
            tone={attentionItems.length > 0 ? "red" : "green"}
            value={String(attentionItems.length)}
          />
          <WorkbenchMetric
            caption="等待人工确认"
            icon={Bell}
            label="活跃预警"
            size="large"
            tone={dashboard.activeAlerts > 0 ? "red" : "green"}
            value={String(dashboard.activeAlerts)}
          />
          <WorkbenchMetric
            caption="当前数据新鲜度"
            icon={RadioTower}
            label="最近采集"
            size="large"
            tone={dashboard.freshness.latestCollectionAt ? "green" : "red"}
            value={latestCollectionLabel}
          />
        </div>
      </section>

      <section
        aria-labelledby="dashboard-attention-heading"
        className="rounded-[var(--radius-4)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 sm:p-5"
        data-testid="dashboard-needs-attention"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-[var(--state-warning)]">
              <AlertTriangle size={14} aria-hidden="true" />
              Needs attention
            </p>
            <h2
              className="mt-1 text-lg font-semibold text-[var(--text-primary)]"
              id="dashboard-attention-heading"
            >
              需要处理
            </h2>
          </div>
          <p className="text-sm text-[var(--text-tertiary)]">
            每一项都给出原因、潜在影响与下一步。
          </p>
        </div>
        {attentionItems.length > 0 ? (
          <div className="mt-4 grid min-w-0 gap-3 lg:grid-cols-2">
            {attentionItems.map((item) => (
              <article
                className="grid min-w-0 gap-3 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                key={item.id}
              >
                <div className="min-w-0">
                  <h3 className="font-semibold text-[var(--text-primary)]">
                    {item.title}
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                    {item.detail}
                  </p>
                </div>
                <Link
                  className="inline-flex min-h-[var(--touch-target)] items-center justify-center gap-2 rounded-[var(--radius-2)] border border-[var(--border-strong)] bg-[var(--surface-primary)] px-3 text-sm font-semibold text-[var(--action-primary)] transition-colors hover:border-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
                  href={item.href}
                >
                  {item.nextAction}
                  <ArrowRight size={14} aria-hidden="true" />
                </Link>
              </article>
            ))}
          </div>
        ) : (
          <div className="mt-4 flex items-start gap-3 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--success-soft)] p-4">
            <CircleCheckBig
              className="mt-0.5 shrink-0 text-[var(--state-success)]"
              size={18}
              aria-hidden="true"
            />
            <div>
              <p className="font-semibold text-[var(--text-primary)]">
                当前没有需要处理的异常
              </p>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                预警、最近失败和过期采集任务均为空。
              </p>
            </div>
          </div>
        )}
      </section>

      <section className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.85fr)]">
        <WorkbenchPanel
          action={
            <Link
              className="text-xs font-semibold text-[var(--action-primary)]"
              href="/intelligence"
            >
              查看全部
            </Link>
          }
          icon={FileText}
          label="洞察"
          subtitle="先看业务结论，再进入可追溯 Evidence。"
          title="优先洞察"
        >
          <div className="grid min-w-0 gap-3">
            {dashboard.topIntelligence.slice(0, 3).map((item, index) => (
              <Link
                className="group rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4 transition-colors hover:border-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
                href={`/intelligence/${item.id}`}
                key={item.id}
              >
                <div className="flex items-start gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--accent-1-soft)] text-xs font-semibold text-[var(--action-primary)]">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3 className="line-clamp-1 text-sm font-semibold text-[var(--text-primary)]">
                      {item.title}
                    </h3>
                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-[var(--text-secondary)]">
                      {item.summary}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <WorkbenchTag>{domainLabels[item.domain] ?? item.domain}</WorkbenchTag>
                      <WorkbenchTag tone="rose">
                        {item.evidenceCount} 条 Evidence
                      </WorkbenchTag>
                      <WorkbenchTag>
                        更新 {formatRelativeTime(item.updatedAt)}
                      </WorkbenchTag>
                    </div>
                  </div>
                  <ArrowRight
                    className="mt-1 shrink-0 text-[var(--action-primary)] transition-transform group-hover:translate-x-0.5"
                    size={16}
                    aria-hidden="true"
                  />
                </div>
              </Link>
            ))}
            {dashboard.topIntelligence.length === 0 ? (
              <p className="rounded-[var(--radius-3)] border border-dashed border-[var(--border-strong)] bg-[var(--surface-secondary)] p-6 text-sm text-[var(--text-tertiary)]">
                当前范围暂无洞察。
              </p>
            ) : null}
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel
          icon={Gauge}
          label="业务闭环"
          subtitle="从可用采集到可交付结果的当前状态。"
          title="闭环进度"
        >
          <div className="grid min-w-0 grid-cols-2 gap-3">
            <WorkbenchMetric
              label="有效采集"
              tone="green"
              value={`${dashboard.taskHealth.enabledTasks} 个任务`}
            />
            <WorkbenchMetric
              label="已识别信号"
              tone="rose"
              value={`${dashboard.domainBreakdown.reduce((sum, item) => sum + item.signalCount, 0)} 条`}
            />
            <WorkbenchMetric
              label="已形成情报"
              tone="violet"
              value={`${dashboard.intelligenceCount} 条`}
            />
            <WorkbenchMetric
              label="最近运行"
              tone="amber"
              value={`${dashboard.recentRuns} 次`}
            />
          </div>
          <Link
            className="mt-4 inline-flex min-h-[var(--touch-target)] w-full items-center justify-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-secondary)] px-4 text-sm font-semibold text-[var(--text-inverse)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
            href="/reports"
          >
            查看交付报告
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </WorkbenchPanel>
      </section>

      <details
        className="group rounded-[var(--radius-4)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] [&_summary::-webkit-details-marker]:hidden"
        data-testid="dashboard-advanced-operations"
      >
        <summary className="flex min-h-[var(--touch-target)] cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] sm:px-5">
          <div>
            <p className="text-xs font-semibold uppercase text-[var(--state-info)]">
              Advanced Operations
            </p>
            <p className="mt-1 font-semibold text-[var(--text-primary)]">
              工程指标、数据结构与方法资产
            </p>
          </div>
          <ChevronDown
            className="shrink-0 text-[var(--text-tertiary)] transition-transform duration-[var(--duration-base)] group-open:rotate-180"
            size={18}
            aria-hidden="true"
          />
        </summary>
        <div className="grid min-w-0 gap-5 border-t border-[var(--border-subtle)] p-4 sm:p-5">
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <WorkbenchMetric
              icon={CheckCircle2}
              label="任务成功率"
              tone="green"
              value={`${formatNumber(dashboard.taskSuccessRate)}%`}
            />
            <WorkbenchMetric
              icon={Database}
              label="字段完整率"
              tone="violet"
              value={`${formatNumber(dashboard.fieldCompleteness)}%`}
            />
            <WorkbenchMetric
              icon={RadioTower}
              label="数据源"
              value={String(dashboard.sourceCount)}
            />
            <WorkbenchMetric
              icon={AlertTriangle}
              label="失败任务"
              tone={dashboard.failedTasks > 0 ? "red" : "green"}
              value={String(dashboard.failedTasks)}
            />
            <WorkbenchMetric
              icon={Gauge}
              label="运行记录"
              value={String(dashboard.recentRuns)}
            />
          </section>

          <TrainingOverviewPanel
            error={trainingOverview.error}
            loading={trainingOverview.loading}
            overview={trainingOverview.overview}
          />

          <section className="grid min-w-0 gap-5 xl:grid-cols-3">
            <WorkbenchPanel
              icon={ShieldAlert}
              label="任务"
              subtitle="运行、失败与数据源覆盖。"
              title="任务健康"
            >
              <div className="grid min-w-0 gap-2 text-sm">
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
                <WorkbenchStatusRow label="数据源数量" value={dashboard.sourceCount} />
              </div>
            </WorkbenchPanel>

            <WorkbenchPanel
              icon={RadioTower}
              label="结构"
              subtitle="当前情报类型占比。"
              title="情报类型"
            >
              <div className="grid min-w-0 gap-4">
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
                  <p className="text-sm text-[var(--text-tertiary)]">暂无类型分布</p>
                ) : null}
              </div>
            </WorkbenchPanel>

            <WorkbenchPanel
              icon={ChartNoAxesCombined}
              label="范围"
              subtitle="当前项目范围内的域分布。"
              title="业务域拆解"
            >
              <div className="grid min-w-0 gap-3">
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
                  <p className="text-sm text-[var(--text-tertiary)]">暂无域内数据</p>
                ) : null}
              </div>
            </WorkbenchPanel>
          </section>
        </div>
      </details>
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
    <section className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4">
      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
        <div className="min-w-0">
          <div className="inline-flex items-center gap-2 rounded-full bg-[var(--warning-soft)] px-3 py-1 text-xs font-semibold text-[var(--state-warning)]">
            <BookOpenCheck size={14} aria-hidden="true" />
            采集方法资产
          </div>
          <h2 className="mt-3 text-base font-semibold text-[var(--text-primary)]">
            数据采集工具与平台方法库
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
            汇总采集工具、平台 SOP、合规边界和证据链，供方案设计与复核。
          </p>
          {error ? (
            <p className="mt-2 text-xs font-semibold text-[var(--state-danger)]">
              {error}
            </p>
          ) : null}
        </div>
        <div className="grid min-w-0 grid-cols-2 gap-2 sm:grid-cols-5 xl:min-w-[32rem]">
          <WorkbenchMetric label="源" value={loading ? "..." : String(metrics?.sourceCount ?? 0)} />
          <WorkbenchMetric label="工具" value={loading ? "..." : String(metrics?.toolCount ?? 0)} />
          <WorkbenchMetric label="方法" value={loading ? "..." : String(metrics?.methodCount ?? 0)} />
          <WorkbenchMetric label="情报" value={loading ? "..." : String(metrics?.intelligenceCount ?? 0)} />
          <WorkbenchMetric label="证据" value={loading ? "..." : String(metrics?.evidenceCount ?? 0)} />
        </div>
      </div>
      <div className="mt-4 grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-4">
        <TrainingLink href="/toolkit" label="打开工具库" />
        <TrainingLink href="/sources" label="查看采集源" />
        <TrainingLink href="/raw-records" label="查看 Evidence" />
        <TrainingLink href="/reports" label="查看报告" />
      </div>
    </section>
  );
}

function TrainingLink({ href, label }: { href: Route; label: string }) {
  return (
    <Link
      className="inline-flex min-h-[var(--touch-target)] items-center justify-center rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 text-sm font-semibold text-[var(--text-secondary)] transition-colors hover:border-[var(--action-primary)] hover:text-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
      href={href}
    >
      {label}
    </Link>
  );
}

function DashboardSkeleton() {
  return (
    <div className="grid gap-5" aria-label="仪表盘加载中" role="status">
      <div className="h-40 animate-pulse rounded-[var(--radius-4)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]" />
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            className="h-32 animate-pulse rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]"
            key={index}
          />
        ))}
      </div>
      <div className="h-72 animate-pulse rounded-[var(--radius-4)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]" />
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
