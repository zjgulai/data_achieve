"use client";

import { AlertTriangle, CheckCircle2, Database, FileText, RadioTower } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { getDashboardOverview } from "@/lib/api/dashboard";
import type { DashboardSummary } from "@/types/dashboard";

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

  if (loading) {
    return <p className="text-sm text-[#6b7280]">加载仪表盘中</p>;
  }

  if (error || !dashboard) {
    return (
      <div className="rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
        {error ?? "Dashboard data not available"}
      </div>
    );
  }

  return (
    <div className="grid gap-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="情报总量" value={dashboard.intelligenceCount} tone="info" />
        <MetricCard label="任务成功率" value={`${dashboard.taskSuccessRate}%`} tone="success" />
        <MetricCard label="字段完整率" value={`${dashboard.fieldCompleteness}%`} tone="neutral" />
        <MetricCard label="失败任务" value={dashboard.failedTasks} tone="risk" />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-lg border border-[#dfe3ea] bg-white p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold">Top Intelligence</h2>
              <p className="mt-1 text-sm text-[#6b7280]">按 final score 排序</p>
            </div>
            <FileText size={20} className="text-[#6b7280]" aria-hidden="true" />
          </div>
          <div className="grid gap-3">
            {dashboard.topIntelligence.map((item) => (
              <Link
                className="rounded-md border border-[#dfe3ea] p-4 transition hover:border-[#94a3b8]"
                href={`/intelligence/${item.id}`}
                key={item.id}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold">{item.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-[#6b7280]">{item.summary}</p>
                  </div>
                  <span className="rounded-md bg-[#ecfeff] px-2.5 py-1 text-sm font-semibold text-[#155e75]">
                    {item.finalScore}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-[#6b7280]">
                  <span className="rounded-md bg-[#f1f5f9] px-2 py-1">{item.domain}</span>
                  <span className="rounded-md bg-[#f1f5f9] px-2 py-1">{item.type}</span>
                  <span className="rounded-md bg-[#f1f5f9] px-2 py-1">{item.status}</span>
                  <span className="rounded-md bg-[#f1f5f9] px-2 py-1">
                    {item.evidenceCount} evidence
                  </span>
                </div>
              </Link>
            ))}
            {dashboard.topIntelligence.length === 0 ? (
              <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
                暂无情报
              </div>
            ) : null}
          </div>
        </div>

        <div className="grid gap-6">
          <Panel title="情报类型" icon={<RadioTower size={20} aria-hidden="true" />}>
            <div className="grid gap-3">
              {dashboard.typeBreakdown.map((item) => (
                <div className="grid gap-2" key={item.type}>
                  <div className="flex items-center justify-between text-sm">
                    <span>{item.type}</span>
                    <span className="font-semibold">{item.count}</span>
                  </div>
                  <div className="h-2 rounded-full bg-[#e5e7eb]">
                    <div
                      className="h-2 rounded-full bg-[#0f766e]"
                      style={{ width: `${item.percent}%` }}
                    />
                  </div>
                </div>
              ))}
              {dashboard.typeBreakdown.length === 0 ? (
                <p className="text-sm text-[#6b7280]">暂无类型分布</p>
              ) : null}
            </div>
          </Panel>

          <Panel title="业务域拆解" icon={<FileText size={20} aria-hidden="true" />}>
            <div className="grid gap-3 text-sm">
              {dashboard.domainBreakdown.map((item) => (
                <div className="rounded-md bg-[#f7f8fa] px-3 py-2" key={item.domain}>
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{item.domain}</span>
                    <span>{item.intelligenceCount} intelligence</span>
                  </div>
                  <p className="mt-1 text-xs text-[#6b7280]">
                    {item.signalCount} signals · {item.projectCount} projects
                  </p>
                </div>
              ))}
              {dashboard.domainBreakdown.length === 0 ? (
                <p className="text-sm text-[#6b7280]">暂无域内数据</p>
              ) : null}
            </div>
          </Panel>

          <Panel title="任务健康" icon={<Database size={20} aria-hidden="true" />}>
            <div className="grid gap-3 text-sm">
              <StatusRow label="任务总数" value={dashboard.taskHealth.totalTasks} />
              <StatusRow label="启用任务" value={dashboard.taskHealth.enabledTasks} />
              <StatusRow label="失败任务" value={dashboard.taskHealth.failedTasks} />
              <StatusRow label="最近运行记录" value={dashboard.taskHealth.recentRuns} />
              <StatusRow label="数据源数量" value={dashboard.sourceCount} />
            </div>
            {dashboard.taskHealth.recentFailures.length > 0 ? (
              <div className="mt-4 grid gap-2">
                {dashboard.taskHealth.recentFailures.map((failure) => (
                  <div className="rounded-md border border-[#fecdd3] bg-[#fff1f2] p-3 text-xs" key={failure.taskId}>
                    <p className="font-semibold text-[#be123c]">{failure.taskName}</p>
                    <p className="mt-1 text-[#6b7280]">{failure.errorMessage ?? "No error message"}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </Panel>
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: "info" | "success" | "neutral" | "risk";
}) {
  const iconMap = {
    info: <RadioTower size={20} aria-hidden="true" />,
    success: <CheckCircle2 size={20} aria-hidden="true" />,
    neutral: <Database size={20} aria-hidden="true" />,
    risk: <AlertTriangle size={20} aria-hidden="true" />,
  };

  return (
    <div className="rounded-lg border border-[#dfe3ea] bg-white p-5">
      <div className="mb-5 flex items-center justify-between text-[#6b7280]">
        <span className="text-sm">{label}</span>
        {iconMap[tone]}
      </div>
      <p className="text-3xl font-semibold">{value}</p>
    </div>
  );
}

function Panel({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold">{title}</h2>
        <span className="text-[#6b7280]">{icon}</span>
      </div>
      {children}
    </section>
  );
}

function StatusRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-[#f7f8fa] px-3 py-2">
      <span className="text-[#6b7280]">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  );
}
