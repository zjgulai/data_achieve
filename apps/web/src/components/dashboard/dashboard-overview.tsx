"use client";

import {
  AlertTriangle,
  ArrowRight,
  Bell,
  ChartNoAxesCombined,
  CheckCircle2,
  Database,
  FileText,
  Gauge,
  RadioTower,
  ShieldAlert,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { getDashboardOverview } from "@/lib/api/dashboard";
import { cn } from "@/lib/utils";
import type { DashboardSummary } from "@/types/dashboard";

type MetricTone = "amber" | "green" | "red" | "rose" | "violet";

const domainLabels: Record<string, string> = {
  competitor: "竞品守望",
  ecommerce: "电商风向",
  osint: "开源雷达",
  social: "社媒脉搏",
};

const domainDescriptions: Record<string, string> = {
  competitor: "页面快照、策略变化、品牌动作",
  ecommerce: "价格排名、商品信号、渠道趋势",
  osint: "GitHub 趋势、开源项目、技术信号",
  social: "内容热度、用户讨论、导入信号",
};

export function DashboardOverview({ domain }: { domain?: string }) {
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
          setError(caught instanceof Error ? caught.message : "Failed to load dashboard");
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
        {error ?? "Dashboard data not available"}
      </div>
    );
  }

  const primaryIntelligence = dashboard.topIntelligence[0] ?? null;

  return (
    <div className="grid min-w-0 gap-5">
      <section className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Pill tone="rose">半月数据周期 2026-06-H1</Pill>
              <Pill tone="neutral">生成 2026/6/12 10:23</Pill>
              <Pill tone={dashboard.activeAlerts > 0 ? "red" : "green"}>
                {dashboard.activeAlerts > 0 ? `${dashboard.activeAlerts} 条活跃预警` : "暂无活跃预警"}
              </Pill>
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

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          delta={`${dashboard.recentRuns} recent runs`}
          icon={RadioTower}
          label="情报总量"
          tone="rose"
          value={dashboard.intelligenceCount}
        />
        <MetricCard
          delta="采集链路"
          icon={CheckCircle2}
          label="任务成功率"
          tone="green"
          value={`${formatNumber(dashboard.taskSuccessRate)}%`}
        />
        <MetricCard
          delta="结构化字段"
          icon={Database}
          label="字段完整率"
          tone="violet"
          value={`${formatNumber(dashboard.fieldCompleteness)}%`}
        />
        <MetricCard
          delta={`${dashboard.sourceCount} sources`}
          icon={Bell}
          label="活跃预警"
          tone={dashboard.activeAlerts > 0 ? "red" : "amber"}
          value={dashboard.activeAlerts}
        />
        <MetricCard
          delta={`${dashboard.taskHealth.enabledTasks} enabled`}
          icon={AlertTriangle}
          label="失败任务"
          tone={dashboard.failedTasks > 0 ? "red" : "green"}
          value={dashboard.failedTasks}
        />
      </section>

      <section className="grid gap-5 2xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
        <Panel
          action={
            <Link className="text-xs font-semibold text-[#C25B6E]" href="/intelligence">
              查看全部
            </Link>
          }
          icon={FileText}
          subtitle="按 final score 排序，优先处理有证据链的信号"
          title="Top Intelligence"
        >
          <div className="grid gap-3">
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
                  <Tag>{domainLabels[item.domain] ?? item.domain}</Tag>
                  <Tag>{item.type}</Tag>
                  <Tag>{item.status}</Tag>
                  <Tag>{item.evidenceCount} evidence</Tag>
                </div>
              </Link>
            ))}
            {dashboard.topIntelligence.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-8 text-sm text-[#86868B]">
                暂无情报
              </div>
            ) : null}
          </div>
        </Panel>

        <div className="grid gap-5">
          <Panel icon={RadioTower} subtitle="类型占比与当前情报结构" title="情报类型">
            <div className="grid gap-4">
              {dashboard.typeBreakdown.map((item) => (
                <DistributionRow
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
          </Panel>

          <Panel icon={ShieldAlert} subtitle="任务可用性与数据源覆盖" title="任务健康">
            <div className="grid gap-2 text-sm">
              <StatusRow label="任务总数" value={dashboard.taskHealth.totalTasks} />
              <StatusRow label="启用任务" value={dashboard.taskHealth.enabledTasks} />
              <StatusRow label="失败任务" tone={dashboard.taskHealth.failedTasks > 0 ? "red" : "green"} value={dashboard.taskHealth.failedTasks} />
              <StatusRow label="最近运行记录" value={dashboard.taskHealth.recentRuns} />
              <StatusRow label="数据源数量" value={dashboard.sourceCount} />
            </div>
            {dashboard.taskHealth.recentFailures.length > 0 ? (
              <div className="mt-4 grid gap-2">
                {dashboard.taskHealth.recentFailures.map((failure) => (
                  <div className="rounded-xl border border-[#FFD7DF] bg-[#FFF7F8] p-3 text-xs" key={failure.taskId}>
                    <p className="font-semibold text-[#C25B6E]">{failure.taskName}</p>
                    <p className="mt-1 leading-5 text-[#7A3D49]">{failure.errorMessage ?? "No error message"}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </Panel>
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel icon={ChartNoAxesCombined} subtitle="四域情报、信号与项目分布" title="业务域拆解">
          <div className="grid gap-3 sm:grid-cols-2">
            {dashboard.domainBreakdown.map((item) => (
              <DomainCard
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
        </Panel>

        <Panel icon={Gauge} subtitle="从采集到报告的闭环状态" title="闭环进度">
          <div className="grid gap-3 sm:grid-cols-4">
            <WorkflowStep label="采集" tone="green" value={`${dashboard.taskHealth.enabledTasks} 个启用任务`} />
            <WorkflowStep label="信号" tone="rose" value={`${dashboard.domainBreakdown.reduce((sum, item) => sum + item.signalCount, 0)} 条信号`} />
            <WorkflowStep label="情报" tone="violet" value={`${dashboard.intelligenceCount} 条情报`} />
            <WorkflowStep label="报告" tone="amber" value={`${dashboard.recentRuns} 次运行`} />
          </div>
        </Panel>
      </section>
    </div>
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

function MetricCard({
  delta,
  icon: Icon,
  label,
  tone,
  value,
}: {
  delta: string;
  icon: LucideIcon;
  label: string;
  tone: MetricTone;
  value: string | number;
}) {
  const toneClasses: Record<MetricTone, string> = {
    amber: "bg-[#FFF4DE] text-[#FF9800]",
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    red: "bg-[#FFE5E2] text-[#FF3B30]",
    rose: "bg-[#FCEBF0] text-[#C25B6E]",
    violet: "bg-[#F5F0FF] text-[#6E5CF6]",
  };

  return (
    <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-[#86868B]">{label}</p>
          <p className="mt-1 text-[11px] font-semibold text-[#C25B6E]">{delta}</p>
        </div>
        <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full", toneClasses[tone])}>
          <Icon size={18} aria-hidden="true" />
        </span>
      </div>
      <p className="text-3xl font-semibold tracking-tight text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function Panel({
  action,
  children,
  icon: Icon,
  subtitle,
  title,
}: {
  action?: ReactNode;
  children: ReactNode;
  icon: LucideIcon;
  subtitle: string;
  title: string;
}) {
  return (
    <section className="min-w-0 rounded-2xl border border-[#E9E5E2] bg-white p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-[#1D1D1F]">{title}</h2>
          <p className="mt-1 text-sm text-[#86868B]">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          {action ? <span className="whitespace-nowrap">{action}</span> : null}
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#FBF8F5] text-[#86868B]">
            <Icon size={16} aria-hidden="true" />
          </span>
        </div>
      </div>
      {children}
    </section>
  );
}

function DistributionRow({
  label,
  tone,
  value,
  width,
}: {
  label: string;
  tone: "rose";
  value: string;
  width: number;
}) {
  const barColor = tone === "rose" ? "bg-[#C25B6E]" : "bg-[#C25B6E]";
  return (
    <div className="grid gap-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-[#5F5757]">{label}</span>
        <span className="font-semibold text-[#1D1D1F]">{value}</span>
      </div>
      <div className="h-2 rounded-full bg-[#F5EDE8]">
        <div className={cn("h-2 rounded-full", barColor)} style={{ width: `${clampPercent(width)}%` }} />
      </div>
    </div>
  );
}

function DomainCard({
  intelligenceCount,
  label,
  projectCount,
  signalCount,
}: {
  intelligenceCount: number;
  label: string;
  projectCount: number;
  signalCount: number;
}) {
  return (
    <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-[#1D1D1F]">{label}</p>
        <span className="rounded-lg bg-white px-2 py-1 text-xs font-semibold text-[#C25B6E]">
          {intelligenceCount} intelligence
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-xl bg-white px-3 py-2">
          <p className="text-[#86868B]">Signals</p>
          <p className="mt-1 text-lg font-semibold text-[#1D1D1F]">{signalCount}</p>
        </div>
        <div className="rounded-xl bg-white px-3 py-2">
          <p className="text-[#86868B]">Projects</p>
          <p className="mt-1 text-lg font-semibold text-[#1D1D1F]">{projectCount}</p>
        </div>
      </div>
    </div>
  );
}

function WorkflowStep({
  label,
  tone,
  value,
}: {
  label: string;
  tone: MetricTone;
  value: string;
}) {
  const toneClasses: Record<MetricTone, string> = {
    amber: "bg-[#FFF4DE] text-[#FF9800]",
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    red: "bg-[#FFE5E2] text-[#FF3B30]",
    rose: "bg-[#FCEBF0] text-[#C25B6E]",
    violet: "bg-[#F5F0FF] text-[#6E5CF6]",
  };
  return (
    <div className="rounded-2xl bg-[#FBF8F5] p-4">
      <span className={cn("mb-3 inline-flex rounded-lg px-2 py-1 text-xs font-semibold", toneClasses[tone])}>
        {label}
      </span>
      <p className="text-sm font-semibold text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function StatusRow({
  label,
  tone = "neutral",
  value,
}: {
  label: string;
  tone?: "green" | "neutral" | "red";
  value: string | number;
}) {
  const valueClass = {
    green: "text-[#2EBA62]",
    neutral: "text-[#1D1D1F]",
    red: "text-[#FF3B30]",
  }[tone];
  return (
    <div className="flex items-center justify-between rounded-xl bg-[#FBF8F5] px-3 py-2">
      <span className="text-[#86868B]">{label}</span>
      <span className={cn("font-semibold", valueClass)}>{value}</span>
    </div>
  );
}

function Pill({ children, tone }: { children: ReactNode; tone: "green" | "neutral" | "red" | "rose" }) {
  const toneClasses = {
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    neutral: "bg-[#FBF8F5] text-[#86868B]",
    red: "bg-[#FFE5E2] text-[#FF3B30]",
    rose: "bg-[#FCEBF0] text-[#C25B6E]",
  };
  return (
    <span className={cn("inline-flex rounded-full px-3 py-1 text-xs font-semibold", toneClasses[tone])}>
      {children}
    </span>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return <span className="rounded-lg bg-white px-2 py-1">{children}</span>;
}

function clampPercent(value: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? value.toString() : value.toFixed(1);
}
