"use client";

import {
  BellRing,
  CalendarDays,
  ChevronDown,
  Clock3,
  FileText,
  History,
  MailCheck,
  PlayCircle,
  PlusCircle,
  RotateCcw,
  Save,
  Send,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { listProjects } from "@/lib/api/projects";
import {
  getEmailChannelStatus,
  testEmailChannel,
} from "@/lib/api/notifications";
import {
  generateReport,
  listReportSubscriptionRuns,
  listReports,
  listReportSubscriptions,
  retryReportSubscriptionRun,
  runReportSubscription,
  sendReport,
  upsertReportSubscription,
} from "@/lib/api/reports";
import { cn } from "@/lib/utils";
import { ReportDetailPanel } from "@/components/reports/report-detail-panel";
import type { Project } from "@/types/project";
import type { EmailChannelStatus } from "@/types/notification";
import type {
  Report,
  ReportDeliveryChannel,
  ReportGenerateInput,
  ReportSubscription,
  ReportSubscriptionRun,
} from "@/types/report";

type StatusFilter = "all" | "generated" | "sent";
type PeriodPreset = "today" | "24h" | "7d" | "custom";

export function ReportsWorkspace() {
  const [reports, setReports] = useState<Report[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [subscriptions, setSubscriptions] = useState<ReportSubscription[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadingReports, setLoadingReports] = useState(true);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingSubscriptions, setLoadingSubscriptions] = useState(true);
  const [loadingEmailChannel, setLoadingEmailChannel] = useState(true);
  const [busy, setBusy] = useState(false);
  const [subscriptionBusy, setSubscriptionBusy] = useState(false);
  const [emailTestBusy, setEmailTestBusy] = useState(false);
  const [runningSubscriptionId, setRunningSubscriptionId] = useState<
    string | null
  >(null);
  const [expandedRunSubscriptionId, setExpandedRunSubscriptionId] = useState<
    string | null
  >(null);
  const [loadingRunHistoryId, setLoadingRunHistoryId] = useState<string | null>(
    null,
  );
  const [retryingRunId, setRetryingRunId] = useState<string | null>(null);
  const [subscriptionRuns, setSubscriptionRuns] = useState<
    Record<string, ReportSubscriptionRun[]>
  >({});
  const [emailChannel, setEmailChannel] = useState<EmailChannelStatus | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [projectFilter, setProjectFilter] = useState("all");
  const [generateProjectId, setGenerateProjectId] = useState("all");
  const [subscriptionProjectId, setSubscriptionProjectId] = useState("all");
  const [subscriptionTime, setSubscriptionTime] = useState("09:00");
  const [subscriptionTimezone, setSubscriptionTimezone] =
    useState("Asia/Shanghai");
  const [subscriptionChannels, setSubscriptionChannels] = useState<
    ReportDeliveryChannel[]
  >(["in_app", "email"]);
  const [subscriptionEnabled, setSubscriptionEnabled] = useState(true);
  const [subscriptionNotice, setSubscriptionNotice] = useState<string | null>(
    null,
  );
  const [emailChannelNotice, setEmailChannelNotice] = useState<string | null>(
    null,
  );
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("today");
  const [customStart, setCustomStart] = useState(() =>
    toDatetimeLocalValue(startOfToday()),
  );
  const [customEnd, setCustomEnd] = useState(() =>
    toDatetimeLocalValue(new Date()),
  );
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    let mounted = true;
    listProjects()
      .then((items) => {
        if (mounted) {
          setProjects(items);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Failed to load projects",
          );
        }
      })
      .finally(() => {
        if (mounted) {
          setLoadingProjects(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    listReportSubscriptions()
      .then((items) => {
        if (mounted) {
          setSubscriptions(items);
          const primary = items[0];
          if (primary) {
            setSubscriptionProjectId(primary.projectId ?? "all");
            setSubscriptionTime(primary.scheduleTime);
            setSubscriptionTimezone(primary.timezone);
            setSubscriptionChannels(primary.channels);
            setSubscriptionEnabled(primary.enabled);
          }
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Failed to load report subscriptions",
          );
        }
      })
      .finally(() => {
        if (mounted) {
          setLoadingSubscriptions(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    getEmailChannelStatus()
      .then((status) => {
        if (mounted) {
          setEmailChannel(status);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(
            caught instanceof Error
              ? caught.message
              : "Failed to load email channel",
          );
        }
      })
      .finally(() => {
        if (mounted) {
          setLoadingEmailChannel(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    setLoadingReports(true);
    listReports(projectFilter === "all" ? undefined : projectFilter)
      .then((items) => {
        if (!mounted) {
          return;
        }
        setReports(items);
        setSelectedId((current) => {
          if (current && items.some((report) => report.id === current)) {
            return current;
          }
          return items[0]?.id ?? null;
        });
      })
      .catch((caught) => {
        if (mounted) {
          setError(
            caught instanceof Error ? caught.message : "Failed to load reports",
          );
        }
      })
      .finally(() => {
        if (mounted) {
          setLoadingReports(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [projectFilter]);

  const filteredReports = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return reports.filter((report) => {
      const matchesStatus =
        statusFilter === "all" || report.status === statusFilter;
      const matchesSearch =
        normalizedSearch.length === 0 ||
        report.title.toLowerCase().includes(normalizedSearch) ||
        report.reportType.toLowerCase().includes(normalizedSearch) ||
        report.content.toLowerCase().includes(normalizedSearch) ||
        projectName(projects, report.projectId)
          .toLowerCase()
          .includes(normalizedSearch);
      return matchesStatus && matchesSearch;
    });
  }, [projects, reports, searchTerm, statusFilter]);

  const selectedReport = useMemo(
    () =>
      reports.find((report) => report.id === selectedId) ??
      filteredReports[0] ??
      null,
    [filteredReports, reports, selectedId],
  );

  const summary = useMemo(() => {
    const generatedCount = reports.filter(
      (report) => report.status === "generated",
    ).length;
    const sentCount = reports.filter(
      (report) => report.status === "sent",
    ).length;
    const latestReport = reports[0] ?? null;
    return {
      generatedCount,
      latestReport,
      sentCount,
      totalCount: reports.length,
    };
  }, [reports]);

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      const payload = buildGeneratePayload({
        customEnd,
        customStart,
        periodPreset,
        projectId: generateProjectId,
      });
      const report = await generateReport(payload);
      const nextFilter = report.projectId ?? "all";
      setProjectFilter(nextFilter);
      setReports((current) => [
        report,
        ...current.filter((item) => item.id !== report.id),
      ]);
      setSelectedId(report.id);
      setStatusFilter("all");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Report generation failed",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSend(report: Report) {
    setBusy(true);
    setError(null);
    try {
      const sent = await sendReport(report.id);
      setReports((current) =>
        current.map((item) => (item.id === sent.id ? sent : item)),
      );
      setSelectedId(sent.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Report send failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveSubscription() {
    if (subscriptionChannels.length === 0) {
      setError("至少选择一个发送渠道");
      return;
    }
    setSubscriptionBusy(true);
    setSubscriptionNotice(null);
    setError(null);
    try {
      const saved = await upsertReportSubscription({
        channels: subscriptionChannels,
        enabled: subscriptionEnabled,
        projectId:
          subscriptionProjectId === "all" ? undefined : subscriptionProjectId,
        reportType: "daily",
        scheduleTime: subscriptionTime,
        timezone: subscriptionTimezone,
      });
      setSubscriptions((current) => {
        const withoutSaved = current.filter((item) => item.id !== saved.id);
        return [saved, ...withoutSaved];
      });
      setSubscriptionNotice("订阅已保存");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Report subscription save failed",
      );
    } finally {
      setSubscriptionBusy(false);
    }
  }

  async function handleRunSubscription(subscriptionId: string) {
    setRunningSubscriptionId(subscriptionId);
    setSubscriptionNotice(null);
    setError(null);
    try {
      const executed = await runReportSubscription(subscriptionId);
      setSubscriptions((current) =>
        current.map((item) => (item.id === executed.id ? executed : item)),
      );
      if (expandedRunSubscriptionId === subscriptionId) {
        await refreshSubscriptionRunHistory(subscriptionId);
      }
      const refreshedReports = await listReports(
        projectFilter === "all" ? undefined : projectFilter,
      );
      setReports(refreshedReports);
      setSelectedId((current) => current ?? refreshedReports[0]?.id ?? null);
      setSubscriptionNotice("订阅已手动执行");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Report subscription run failed",
      );
    } finally {
      setRunningSubscriptionId(null);
    }
  }

  async function refreshSubscriptionRunHistory(subscriptionId: string) {
    const runs = await listReportSubscriptionRuns(subscriptionId);
    setSubscriptionRuns((current) => ({ ...current, [subscriptionId]: runs }));
    return runs;
  }

  async function handleToggleRunHistory(subscriptionId: string) {
    if (expandedRunSubscriptionId === subscriptionId) {
      setExpandedRunSubscriptionId(null);
      return;
    }
    setExpandedRunSubscriptionId(subscriptionId);
    setLoadingRunHistoryId(subscriptionId);
    setError(null);
    try {
      await refreshSubscriptionRunHistory(subscriptionId);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Report subscription history failed",
      );
    } finally {
      setLoadingRunHistoryId(null);
    }
  }

  async function handleRetrySubscriptionRun(
    subscriptionId: string,
    runId: string,
  ) {
    setRetryingRunId(runId);
    setSubscriptionNotice(null);
    setError(null);
    try {
      const retried = await retryReportSubscriptionRun(subscriptionId, runId);
      setSubscriptions((current) =>
        current.map((item) => (item.id === retried.id ? retried : item)),
      );
      await refreshSubscriptionRunHistory(subscriptionId);
      const refreshedReports = await listReports(
        projectFilter === "all" ? undefined : projectFilter,
      );
      setReports(refreshedReports);
      setSelectedId((current) => current ?? refreshedReports[0]?.id ?? null);
      setSubscriptionNotice("订阅已重试");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Report subscription retry failed",
      );
    } finally {
      setRetryingRunId(null);
    }
  }

  async function handleTestEmailChannel() {
    setEmailTestBusy(true);
    setEmailChannelNotice(null);
    setError(null);
    try {
      const result = await testEmailChannel();
      setEmailChannel(result.status);
      setEmailChannelNotice(
        result.delivered
          ? `测试邮件已发送至 ${result.recipientEmail}`
          : `测试未发送：${emailReasonLabel(result.reason)}`,
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Email channel test failed",
      );
    } finally {
      setEmailTestBusy(false);
    }
  }

  function toggleSubscriptionChannel(channel: ReportDeliveryChannel) {
    setSubscriptionChannels((current) =>
      current.includes(channel)
        ? current.filter((item) => item !== channel)
        : [...current, channel],
    );
  }

  return (
    <div className="grid min-w-0 gap-5">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          icon={FileText}
          label="报告总数"
          tone="rose"
          value={summary.totalCount}
        />
        <SummaryCard
          icon={Clock3}
          label="待发送"
          tone="amber"
          value={summary.generatedCount}
        />
        <SummaryCard
          icon={MailCheck}
          label="已发送"
          tone="green"
          value={summary.sentCount}
        />
        <SummaryCard
          icon={CalendarDays}
          label="最新生成"
          tone="violet"
          value={
            summary.latestReport
              ? formatShortDate(summary.latestReport.createdAt)
              : "-"
          }
        />
      </section>

      <details className="group rounded-2xl border border-[#E9E5E2] bg-white">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-5 marker:hidden">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Pill tone="rose">Daily Report</Pill>
              <Pill tone="neutral">
                {summary.latestReport
                  ? `${formatDate(summary.latestReport.periodStart)} 至 ${formatDate(summary.latestReport.periodEnd)}`
                  : "暂无周期"}
              </Pill>
              <Pill tone={summary.generatedCount > 0 ? "amber" : "green"}>
                {summary.generatedCount > 0
                  ? `${summary.generatedCount} 份待发送`
                  : "发送队列清爽"}
              </Pill>
            </div>
            <h2 className="text-base font-semibold text-[#1D1D1F]">报告生成</h2>
            <p className="mt-1 text-sm leading-6 text-[#86868B]">
              按项目和周期生成新的日报，正文与证据引用会进入下方报告队列。
            </p>
          </div>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#FBF8F5] text-[#C25B6E]">
            <ChevronDown
              className="transition-transform group-open:rotate-180"
              size={17}
              aria-hidden="true"
            />
          </span>
        </summary>
        <div className="border-t border-[#EDE6DF] p-5">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px] xl:items-end">
            <div className="min-w-0">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Pill tone="rose">Daily Report</Pill>
                <Pill tone="neutral">
                  {summary.latestReport
                    ? `${formatDate(summary.latestReport.periodStart)} 至 ${formatDate(summary.latestReport.periodEnd)}`
                    : "暂无周期"}
                </Pill>
                <Pill tone={summary.generatedCount > 0 ? "amber" : "green"}>
                  {summary.generatedCount > 0
                    ? `${summary.generatedCount} 份待发送`
                    : "发送队列清爽"}
                </Pill>
              </div>
              <h2 className="text-2xl font-semibold tracking-tight text-[#1D1D1F]">
                报告阅读工作台
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#86868B]">
                汇总日报、保留情报 ID 与证据数量，并支持按项目和周期生成报告。
              </p>
            </div>

            <div className="grid gap-3 rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="生成项目">
                  <select
                    className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm outline-none"
                    disabled={loadingProjects}
                    onChange={(event) =>
                      setGenerateProjectId(event.target.value)
                    }
                    value={generateProjectId}
                  >
                    <option value="all">全局</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="生成周期">
                  <select
                    className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm outline-none"
                    onChange={(event) =>
                      setPeriodPreset(event.target.value as PeriodPreset)
                    }
                    value={periodPreset}
                  >
                    <option value="today">今天</option>
                    <option value="24h">过去 24 小时</option>
                    <option value="7d">过去 7 天</option>
                    <option value="custom">自定义</option>
                  </select>
                </Field>
              </div>
              {periodPreset === "custom" ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="周期开始">
                    <input
                      className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm outline-none"
                      onChange={(event) => setCustomStart(event.target.value)}
                      type="datetime-local"
                      value={customStart}
                    />
                  </Field>
                  <Field label="周期结束">
                    <input
                      className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-white px-3 text-sm outline-none"
                      onChange={(event) => setCustomEnd(event.target.value)}
                      type="datetime-local"
                      value={customEnd}
                    />
                  </Field>
                </div>
              ) : null}
              <button
                className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-[#C25B6E] px-4 text-sm font-semibold text-white transition-colors hover:bg-[#A8495B] disabled:cursor-not-allowed disabled:opacity-60"
                disabled={busy}
                onClick={() => void handleGenerate()}
                type="button"
              >
                <PlusCircle size={17} aria-hidden="true" />
                生成日报
              </button>
            </div>
          </div>
        </div>
      </details>

      <details className="group rounded-2xl border border-[#E9E5E2] bg-white">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 p-5 marker:hidden">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#FCEBF0] text-[#C25B6E]">
              <BellRing size={17} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-[#1D1D1F]">
                自动分发
              </h2>
              <p className="mt-1 text-sm leading-6 text-[#86868B]">
                配置日报发送时间、站内通知和邮件通道。
              </p>
            </div>
          </div>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#FBF8F5] text-[#C25B6E]">
            <ChevronDown
              className="transition-transform group-open:rotate-180"
              size={17}
              aria-hidden="true"
            />
          </span>
        </summary>
        <div className="grid gap-4 border-t border-[#EDE6DF] p-5 xl:grid-cols-[minmax(0,1fr)_minmax(280px,420px)]">
          <div className="min-w-0">
            <div className="mb-3 flex items-center gap-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#FCEBF0] text-[#C25B6E]">
                <BellRing size={17} aria-hidden="true" />
              </span>
              <div>
                <h2 className="text-base font-semibold text-[#1D1D1F]">
                  自动分发
                </h2>
                <p className="mt-1 text-sm text-[#86868B]">
                  配置每日生成后的触达时间和渠道偏好
                </p>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              <Field label="订阅项目">
                <select
                  className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm outline-none"
                  disabled={loadingProjects}
                  onChange={(event) =>
                    setSubscriptionProjectId(event.target.value)
                  }
                  value={subscriptionProjectId}
                >
                  <option value="all">全局</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="发送时间">
                <input
                  className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm outline-none"
                  onChange={(event) => setSubscriptionTime(event.target.value)}
                  type="time"
                  value={subscriptionTime}
                />
              </Field>
              <Field label="时区">
                <select
                  className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm outline-none"
                  onChange={(event) =>
                    setSubscriptionTimezone(event.target.value)
                  }
                  value={subscriptionTimezone}
                >
                  <option value="Asia/Shanghai">Asia/Shanghai</option>
                  <option value="UTC">UTC</option>
                  <option value="America/Los_Angeles">
                    America/Los_Angeles
                  </option>
                </select>
              </Field>
              <Field label="状态">
                <select
                  className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm outline-none"
                  onChange={(event) =>
                    setSubscriptionEnabled(event.target.value === "enabled")
                  }
                  value={subscriptionEnabled ? "enabled" : "disabled"}
                >
                  <option value="enabled">启用</option>
                  <option value="disabled">暂停</option>
                </select>
              </Field>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              {(["in_app", "email"] as const).map((channel) => (
                <label
                  className="inline-flex h-9 items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm font-medium text-[#1D1D1F]"
                  key={channel}
                >
                  <input
                    aria-label={channel === "in_app" ? "站内通知" : "邮件"}
                    checked={subscriptionChannels.includes(channel)}
                    className="h-4 w-4 accent-[#C25B6E]"
                    onChange={() => toggleSubscriptionChannel(channel)}
                    type="checkbox"
                  />
                  {channelLabel(channel)}
                </label>
              ))}
              <button
                className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-[#1D1D1F] px-4 text-sm font-semibold text-white transition-colors hover:bg-[#3A3A3C] disabled:cursor-not-allowed disabled:opacity-60"
                disabled={subscriptionBusy || loadingSubscriptions}
                onClick={() => void handleSaveSubscription()}
                type="button"
              >
                <Save size={16} aria-hidden="true" />
                保存订阅
              </button>
              {subscriptionNotice ? (
                <span className="text-sm font-medium text-[#2EBA62]">
                  {subscriptionNotice}
                </span>
              ) : null}
            </div>

            <div className="mt-3 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-[#C25B6E]">
                      <MailCheck size={15} aria-hidden="true" />
                    </span>
                    <p className="text-sm font-semibold text-[#1D1D1F]">
                      邮件通道诊断
                    </p>
                    <StatusPill status={emailChannel?.status ?? "checking"} />
                  </div>
                  <p className="mt-2 text-xs leading-5 text-[#86868B]">
                    {loadingEmailChannel
                      ? "正在读取 SMTP 配置状态"
                      : emailChannelDescription(emailChannel)}
                  </p>
                </div>
                <button
                  className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-[#EDE6DF] bg-white px-3 text-xs font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={emailTestBusy || loadingEmailChannel}
                  onClick={() => void handleTestEmailChannel()}
                  type="button"
                >
                  <Send size={14} aria-hidden="true" />
                  {emailTestBusy ? "测试中" : "测试邮件"}
                </button>
              </div>
              {emailChannel ? (
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-[#86868B]">
                  <Tag>
                    {emailChannel.hostConfigured
                      ? "SMTP host 已配置"
                      : "缺少 SMTP host"}
                  </Tag>
                  <Tag>
                    {emailChannel.senderConfigured
                      ? "发件人已配置"
                      : "缺少发件人"}
                  </Tag>
                  <Tag>
                    {emailChannel.authConfigured ? "认证已配置" : "未启用认证"}
                  </Tag>
                  <Tag>
                    {emailChannel.tlsMode.toUpperCase()} · {emailChannel.port}
                  </Tag>
                </div>
              ) : null}
              {emailChannelNotice ? (
                <p
                  className={cn(
                    "mt-2 text-xs font-medium",
                    emailChannel?.configured
                      ? "text-[#2EBA62]"
                      : "text-[#C25B6E]",
                  )}
                >
                  {emailChannelNotice}
                </p>
              ) : null}
            </div>
          </div>

          <div className="min-w-0 rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-[#1D1D1F]">已配置订阅</p>
              <Pill
                tone={
                  subscriptions.some((item) => item.enabled)
                    ? "green"
                    : "neutral"
                }
              >
                {subscriptions.filter((item) => item.enabled).length} 个启用
              </Pill>
            </div>
            <div className="mt-3 grid gap-2">
              {loadingSubscriptions ? (
                <p className="text-sm text-[#86868B]">加载订阅中</p>
              ) : null}
              {!loadingSubscriptions && subscriptions.length === 0 ? (
                <p className="rounded-xl border border-dashed border-[#EDE6DF] bg-white p-3 text-sm text-[#86868B]">
                  暂无自动分发订阅
                </p>
              ) : null}
              {subscriptions.slice(0, 3).map((subscription) => (
                <div className="rounded-xl bg-white p-3" key={subscription.id}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-[#1D1D1F]">
                        {projectName(projects, subscription.projectId)} ·{" "}
                        {subscription.scheduleTime}
                      </p>
                      <p className="mt-1 text-xs text-[#86868B]">
                        {subscription.channels.map(channelLabel).join(" + ")}
                        {subscription.nextRunAt
                          ? ` · 下次 ${formatDate(subscription.nextRunAt)}`
                          : " · 已暂停"}
                      </p>
                    </div>
                    <StatusPill
                      status={subscription.enabled ? "enabled" : "paused"}
                    />
                  </div>
                  <div className="mt-3 grid gap-2 rounded-xl bg-[#FBF8F5] p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold text-[#86868B]">
                        最近执行
                      </p>
                      <StatusPill
                        status={subscription.latestRun?.status ?? "not_run"}
                      />
                    </div>
                    <p className="text-xs leading-5 text-[#86868B]">
                      {subscription.latestRun
                        ? `${triggerLabel(subscription.latestRun.triggerType)} · ${formatDate(subscription.latestRun.startedAt)}`
                        : "暂无执行记录"}
                    </p>
                    {subscription.latestRun?.errorMessage ? (
                      <p className="text-xs leading-5 text-[#C25B6E]">
                        {runIssueSummary(subscription.latestRun.errorMessage)}
                      </p>
                    ) : null}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs text-[#86868B]">
                        {subscription.lastSentAt
                          ? `上次 ${formatDate(subscription.lastSentAt)}`
                          : "尚未成功发送"}
                      </p>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-[#EDE6DF] bg-white px-3 text-xs font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={loadingRunHistoryId === subscription.id}
                          onClick={() =>
                            void handleToggleRunHistory(subscription.id)
                          }
                          type="button"
                        >
                          <History size={14} aria-hidden="true" />
                          {expandedRunSubscriptionId === subscription.id
                            ? "收起历史"
                            : "执行历史"}
                        </button>
                        <button
                          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-[#EDE6DF] bg-white px-3 text-xs font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={runningSubscriptionId === subscription.id}
                          onClick={() =>
                            void handleRunSubscription(subscription.id)
                          }
                          type="button"
                        >
                          <PlayCircle size={14} aria-hidden="true" />
                          {runningSubscriptionId === subscription.id
                            ? "执行中"
                            : "立即执行"}
                        </button>
                      </div>
                    </div>
                    {expandedRunSubscriptionId === subscription.id ? (
                      <div className="grid gap-2 border-t border-[#EDE6DF] pt-2">
                        {loadingRunHistoryId === subscription.id ? (
                          <p className="text-xs text-[#86868B]">加载执行历史</p>
                        ) : null}
                        {loadingRunHistoryId !== subscription.id &&
                        (subscriptionRuns[subscription.id] ?? []).length ===
                          0 ? (
                          <p className="text-xs text-[#86868B]">暂无执行历史</p>
                        ) : null}
                        {(subscriptionRuns[subscription.id] ?? []).map(
                          (run) => (
                            <div
                              className="rounded-lg border border-[#EDE6DF] bg-white p-2"
                              key={run.id}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <p className="text-xs font-semibold text-[#1D1D1F]">
                                    {triggerLabel(run.triggerType)} ·{" "}
                                    {formatDate(run.startedAt)}
                                  </p>
                                  <p className="mt-1 text-xs leading-5 text-[#86868B]">
                                    {runDeliverySummary(run)}
                                  </p>
                                </div>
                                <StatusPill status={run.status} />
                              </div>
                              {run.errorMessage ? (
                                <p className="mt-1 text-xs leading-5 text-[#C25B6E]">
                                  {runIssueSummary(run.errorMessage)}
                                </p>
                              ) : null}
                              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                                <p className="text-xs text-[#86868B]">
                                  {run.finishedAt
                                    ? `完成 ${formatDate(run.finishedAt)}`
                                    : "仍在执行"}
                                </p>
                                {canRetryRun(run.status) ? (
                                  <button
                                    className="inline-flex h-7 items-center justify-center gap-1.5 rounded-lg border border-[#F1D5DA] bg-[#FFF7F8] px-2.5 text-xs font-semibold text-[#C25B6E] transition-colors hover:bg-[#FCEBF0] disabled:cursor-not-allowed disabled:opacity-60"
                                    disabled={retryingRunId === run.id}
                                    onClick={() =>
                                      void handleRetrySubscriptionRun(
                                        subscription.id,
                                        run.id,
                                      )
                                    }
                                    type="button"
                                  >
                                    <RotateCcw size={13} aria-hidden="true" />
                                    {retryingRunId === run.id
                                      ? "重试中"
                                      : "重试"}
                                  </button>
                                ) : null}
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </details>

      {error ? (
        <p className="rounded-2xl border border-[#FFD7DF] bg-[#FFF7F8] px-4 py-3 text-sm text-[#C25B6E]">
          {error}
        </p>
      ) : null}

      <div className="grid min-w-0 gap-5 2xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="min-w-0 rounded-2xl border border-[#E9E5E2] bg-white">
          <div className="border-b border-[#EDE6DF] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-[#1D1D1F]">
                  报告队列
                </h2>
                <p className="mt-1 text-sm text-[#86868B]">
                  按项目、状态、关键字定位日报
                </p>
              </div>
              <SlidersHorizontal
                size={18}
                className="text-[#86868B]"
                aria-hidden="true"
              />
            </div>

            <div className="mt-4 grid gap-3">
              <Field label="报告筛选项目">
                <select
                  className="h-10 w-full rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm outline-none"
                  disabled={loadingProjects}
                  onChange={(event) => setProjectFilter(event.target.value)}
                  value={projectFilter}
                >
                  <option value="all">全部项目</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="flex rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-1">
                {[
                  { label: "全部", value: "all" },
                  { label: "待发送", value: "generated" },
                  { label: "已发送", value: "sent" },
                ].map((item) => (
                  <button
                    className={cn(
                      "h-8 flex-1 rounded-lg text-xs font-semibold transition-colors",
                      statusFilter === item.value
                        ? "bg-white text-[#C25B6E]"
                        : "text-[#86868B] hover:text-[#1D1D1F]",
                    )}
                    key={item.value}
                    onClick={() => setStatusFilter(item.value as StatusFilter)}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <label className="flex h-10 items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 text-sm text-[#86868B]">
                <Search size={16} aria-hidden="true" />
                <input
                  className="w-full border-0 bg-transparent outline-none"
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="搜索标题、项目、正文..."
                  type="search"
                  value={searchTerm}
                />
              </label>
            </div>
          </div>

          <div className="grid gap-3 p-4">
            {loadingReports ? (
              <p className="px-1 py-4 text-sm text-[#86868B]">加载报告中</p>
            ) : null}
            {filteredReports.map((report) => (
              <article
                className={cn(
                  "rounded-2xl border p-4 transition-colors",
                  report.id === selectedReport?.id
                    ? "border-[#C25B6E] bg-[#FFF7F8]"
                    : "border-[#EDE6DF] bg-[#FBF8F5] hover:border-[#C25B6E]",
                )}
                key={report.id}
              >
                <button
                  className="w-full text-left"
                  onClick={() => setSelectedId(report.id)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="line-clamp-2 text-sm font-semibold leading-6 text-[#1D1D1F]">
                        {report.title}
                      </h3>
                      <p className="mt-1 text-xs leading-5 text-[#86868B]">
                        {formatDate(report.periodStart)} 至{" "}
                        {formatDate(report.periodEnd)}
                      </p>
                    </div>
                    <StatusPill status={report.status} />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-[#86868B]">
                    <Tag>{projectName(projects, report.projectId)}</Tag>
                    <Tag>{report.reportType}</Tag>
                    <Tag>{estimateReadingMinutes(report.content)} min read</Tag>
                    <Tag>
                      {countEvidenceMentions(report.content)} evidence refs
                    </Tag>
                  </div>
                </button>
                <Link
                  className="mt-3 inline-flex text-xs font-semibold text-[#C25B6E]"
                  href={`/reports/${report.id}` as Route}
                >
                  打开详情页
                </Link>
              </article>
            ))}
            {!loadingReports && filteredReports.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-8 text-sm text-[#86868B]">
                当前筛选条件下暂无报告
              </div>
            ) : null}
          </div>
        </section>

        {selectedReport ? (
          <ReportDetailPanel
            busy={busy}
            onSend={handleSend}
            report={selectedReport}
            showOpenLink
          />
        ) : (
          <div className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-8 text-sm text-[#86868B]">
            选择一份报告查看正文
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  tone,
  value,
}: {
  icon: typeof FileText;
  label: string;
  tone: "amber" | "green" | "rose" | "violet";
  value: string | number;
}) {
  const toneClasses = {
    amber: "bg-[#FFF4DE] text-[#FF9800]",
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    rose: "bg-[#FCEBF0] text-[#C25B6E]",
    violet: "bg-[#F5F0FF] text-[#6E5CF6]",
  };
  return (
    <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
      <div className="mb-5 flex items-center justify-between gap-3">
        <p className="text-xs font-medium text-[#86868B]">{label}</p>
        <span
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-full",
            toneClasses[tone],
          )}
        >
          <Icon size={18} aria-hidden="true" />
        </span>
      </div>
      <p className="text-3xl font-semibold tracking-tight text-[#1D1D1F]">
        {value}
      </p>
    </div>
  );
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="grid gap-1.5 text-xs font-semibold text-[#86868B]">
      {label}
      {children}
    </label>
  );
}

function StatusPill({ status }: { status: string }) {
  const statusMeta: Record<string, { className: string; label: string }> = {
    checking: { className: "bg-[#FBF8F5] text-[#86868B]", label: "检查中" },
    enabled: { className: "bg-[#EAF8EE] text-[#2EBA62]", label: "启用" },
    failed: { className: "bg-[#FFF7F8] text-[#C25B6E]", label: "失败" },
    generated: { className: "bg-[#FFF4DE] text-[#FF9800]", label: "待发送" },
    misconfigured: {
      className: "bg-[#FFF4DE] text-[#FF9800]",
      label: "配置不完整",
    },
    not_run: { className: "bg-[#FBF8F5] text-[#86868B]", label: "未执行" },
    not_configured: {
      className: "bg-[#FFF7F8] text-[#C25B6E]",
      label: "未配置",
    },
    partial_success: {
      className: "bg-[#FFF4DE] text-[#FF9800]",
      label: "部分成功",
    },
    paused: { className: "bg-[#FBF8F5] text-[#86868B]", label: "暂停" },
    ready: { className: "bg-[#EAF8EE] text-[#2EBA62]", label: "可测试" },
    running: { className: "bg-[#F5F0FF] text-[#6E5CF6]", label: "执行中" },
    sent: { className: "bg-[#EAF8EE] text-[#2EBA62]", label: "已发送" },
    success: { className: "bg-[#EAF8EE] text-[#2EBA62]", label: "成功" },
  };
  const meta = statusMeta[status] ?? {
    className: "bg-[#FBF8F5] text-[#86868B]",
    label: status,
  };
  return (
    <span
      className={cn(
        "rounded-lg px-2.5 py-1 text-xs font-semibold",
        meta.className,
      )}
    >
      {meta.label}
    </span>
  );
}

function Pill({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "amber" | "green" | "neutral" | "rose";
}) {
  const toneClasses = {
    amber: "bg-[#FFF4DE] text-[#FF9800]",
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    neutral: "bg-[#FBF8F5] text-[#86868B]",
    rose: "bg-[#FCEBF0] text-[#C25B6E]",
  };
  return (
    <span
      className={cn(
        "rounded-full px-3 py-1 text-xs font-semibold",
        toneClasses[tone],
      )}
    >
      {children}
    </span>
  );
}

function Tag({ children }: { children: ReactNode }) {
  return <span className="rounded-lg bg-white px-2 py-1">{children}</span>;
}

function buildGeneratePayload({
  customEnd,
  customStart,
  periodPreset,
  projectId,
}: {
  customEnd: string;
  customStart: string;
  periodPreset: PeriodPreset;
  projectId: string;
}): ReportGenerateInput {
  const now = new Date();
  let start: Date;
  let end = now;

  if (periodPreset === "today") {
    start = startOfToday();
  } else if (periodPreset === "24h") {
    start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  } else if (periodPreset === "7d") {
    start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  } else {
    start = new Date(customStart);
    end = new Date(customEnd);
  }

  if (
    Number.isNaN(start.getTime()) ||
    Number.isNaN(end.getTime()) ||
    end <= start
  ) {
    throw new Error("报告周期不合法");
  }

  return {
    projectId: projectId === "all" ? undefined : projectId,
    reportType: "daily",
    periodEnd: end.toISOString(),
    periodStart: start.toISOString(),
  };
}

function startOfToday() {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return date;
}

function toDatetimeLocalValue(value: Date) {
  const offset = value.getTimezoneOffset();
  const local = new Date(value.getTime() - offset * 60 * 1000);
  return local.toISOString().slice(0, 16);
}

function projectName(projects: Project[], projectId: string | null) {
  if (!projectId) {
    return "全局";
  }
  return (
    projects.find((project) => project.id === projectId)?.name ?? "未知项目"
  );
}

function estimateReadingMinutes(content: string) {
  const words = content.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(words / 180));
}

function countEvidenceMentions(content: string) {
  const matches = content.match(/证据数|evidence/gi);
  return matches?.length ?? 0;
}

function channelLabel(channel: ReportDeliveryChannel) {
  return channelText(channel);
}

function triggerLabel(triggerType: string) {
  if (triggerType === "manual") {
    return "手动触发";
  }
  if (triggerType === "retry") {
    return "失败重试";
  }
  return "自动调度";
}

function runIssueSummary(errorMessage: string) {
  return errorMessage
    .replaceAll("smtp_auth_incomplete", "SMTP 认证配置不完整")
    .replaceAll("smtp_not_configured", "SMTP 未配置");
}

function canRetryRun(status: string) {
  return status === "failed" || status === "partial_success";
}

function emailChannelDescription(status: EmailChannelStatus | null) {
  if (!status) {
    return "邮件通道状态暂不可用";
  }
  if (status.configured) {
    return `SMTP 配置完整，当前使用 ${status.tlsMode.toUpperCase()}，端口 ${status.port}。`;
  }
  const missing =
    status.missingSettings.length > 0
      ? status.missingSettings.join("、")
      : "必要配置";
  return `${emailReasonLabel(status.reason)}：${missing}。邮件订阅会继续发送站内通知，并跳过邮件渠道。`;
}

function emailReasonLabel(reason: string | null) {
  if (reason === "smtp_auth_incomplete") {
    return "SMTP 认证配置不完整";
  }
  if (reason === "smtp_not_configured") {
    return "SMTP 未配置";
  }
  if (!reason) {
    return "无错误";
  }
  return reason;
}

function runDeliverySummary(run: ReportSubscriptionRun) {
  const delivered = run.deliveredChannels.map(channelText).join("、") || "无";
  const skipped = Object.keys(run.skippedChannels).map(channelText).join("、");
  return skipped
    ? `已送达 ${delivered} · 未送达 ${skipped}`
    : `已送达 ${delivered}`;
}

function channelText(channel: string) {
  return channel === "email" ? "邮件" : "站内通知";
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatShortDate(value: string) {
  return new Date(value).toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
}
