"use client";

import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  FileText,
  MailCheck,
  PlusCircle,
  Search,
  Send,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { generateReport, listReports, sendReport } from "@/lib/api/reports";
import { cn } from "@/lib/utils";
import type { Report } from "@/types/report";

type StatusFilter = "all" | "generated" | "sent";

export function ReportsWorkspace() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    let mounted = true;
    listReports()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setReports(items);
        setSelectedId(items[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load reports");
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
  }, []);

  const filteredReports = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return reports.filter((report) => {
      const matchesStatus = statusFilter === "all" || report.status === statusFilter;
      const matchesSearch =
        normalizedSearch.length === 0 ||
        report.title.toLowerCase().includes(normalizedSearch) ||
        report.reportType.toLowerCase().includes(normalizedSearch) ||
        report.content.toLowerCase().includes(normalizedSearch);
      return matchesStatus && matchesSearch;
    });
  }, [reports, searchTerm, statusFilter]);

  const selectedReport = useMemo(
    () => reports.find((report) => report.id === selectedId) ?? filteredReports[0] ?? null,
    [filteredReports, reports, selectedId],
  );

  const summary = useMemo(() => {
    const generatedCount = reports.filter((report) => report.status === "generated").length;
    const sentCount = reports.filter((report) => report.status === "sent").length;
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
      const report = await generateReport({ reportType: "daily" });
      setReports((current) => [report, ...current.filter((item) => item.id !== report.id)]);
      setSelectedId(report.id);
      setStatusFilter("all");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Report generation failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleSend(report: Report) {
    setBusy(true);
    setError(null);
    try {
      const sent = await sendReport(report.id);
      setReports((current) => current.map((item) => (item.id === sent.id ? sent : item)));
      setSelectedId(sent.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Report send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-w-0 gap-5">
      <section className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Pill tone="rose">Daily Report</Pill>
              <Pill tone="neutral">
                {summary.latestReport
                  ? `${formatDate(summary.latestReport.periodStart)} 至 ${formatDate(summary.latestReport.periodEnd)}`
                  : "暂无周期"}
              </Pill>
              <Pill tone={summary.generatedCount > 0 ? "amber" : "green"}>
                {summary.generatedCount > 0 ? `${summary.generatedCount} 份待发送` : "发送队列清爽"}
              </Pill>
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-[#1D1D1F]">报告阅读工作台</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#86868B]">
              汇总日报、保留情报 ID 与证据数量，并支持生成、筛选、阅读和发送。
            </p>
          </div>
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
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard icon={FileText} label="报告总数" tone="rose" value={summary.totalCount} />
        <SummaryCard icon={Clock3} label="待发送" tone="amber" value={summary.generatedCount} />
        <SummaryCard icon={MailCheck} label="已发送" tone="green" value={summary.sentCount} />
        <SummaryCard
          icon={CalendarDays}
          label="最新生成"
          tone="violet"
          value={summary.latestReport ? formatShortDate(summary.latestReport.createdAt) : "-"}
        />
      </section>

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
                <h2 className="text-base font-semibold text-[#1D1D1F]">报告队列</h2>
                <p className="mt-1 text-sm text-[#86868B]">按状态筛选，快速定位可发送日报</p>
              </div>
              <FileText size={18} className="text-[#86868B]" aria-hidden="true" />
            </div>

            <div className="mt-4 grid gap-3">
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
                  placeholder="搜索标题、类型、正文..."
                  type="search"
                  value={searchTerm}
                />
              </label>
            </div>
          </div>

          <div className="grid gap-3 p-4">
            {loading ? <p className="px-1 py-4 text-sm text-[#86868B]">加载报告中</p> : null}
            {filteredReports.map((report) => (
              <button
                className={cn(
                  "rounded-2xl border p-4 text-left transition-colors",
                  report.id === selectedReport?.id
                    ? "border-[#C25B6E] bg-[#FFF7F8]"
                    : "border-[#EDE6DF] bg-[#FBF8F5] hover:border-[#C25B6E]",
                )}
                key={report.id}
                onClick={() => setSelectedId(report.id)}
                type="button"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="line-clamp-2 text-sm font-semibold leading-6 text-[#1D1D1F]">
                      {report.title}
                    </h3>
                    <p className="mt-1 text-xs leading-5 text-[#86868B]">
                      {formatDate(report.periodStart)} 至 {formatDate(report.periodEnd)}
                    </p>
                  </div>
                  <StatusPill status={report.status} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs text-[#86868B]">
                  <Tag>{report.reportType}</Tag>
                  <Tag>{estimateReadingMinutes(report.content)} min read</Tag>
                  <Tag>{countEvidenceMentions(report.content)} evidence refs</Tag>
                </div>
              </button>
            ))}
            {!loading && filteredReports.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-8 text-sm text-[#86868B]">
                当前筛选条件下暂无报告
              </div>
            ) : null}
          </div>
        </section>

        <section className="min-w-0 rounded-2xl border border-[#E9E5E2] bg-white">
          {selectedReport ? (
            <div className="grid gap-0">
              <div className="border-b border-[#EDE6DF] p-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <StatusPill status={selectedReport.status} />
                      <Pill tone="neutral">{selectedReport.reportType}</Pill>
                      <Pill tone="rose">{estimateReadingMinutes(selectedReport.content)} min read</Pill>
                    </div>
                    <h2 className="text-xl font-semibold tracking-tight text-[#1D1D1F]">
                      {selectedReport.title}
                    </h2>
                    <p className="mt-2 text-sm text-[#86868B]">
                      {formatDate(selectedReport.periodStart)} 至 {formatDate(selectedReport.periodEnd)}
                    </p>
                  </div>
                  <button
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-4 text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={busy || selectedReport.status === "sent"}
                    onClick={() => void handleSend(selectedReport)}
                    type="button"
                  >
                    {selectedReport.status === "sent" ? (
                      <CheckCircle2 size={16} aria-hidden="true" />
                    ) : (
                      <Send size={16} aria-hidden="true" />
                    )}
                    {selectedReport.status === "sent" ? "已发送" : "发送报告"}
                  </button>
                </div>
              </div>

              <div className="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_260px]">
                <article className="min-w-0 rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-5">
                  <ReportMarkdown content={selectedReport.content} />
                </article>

                <aside className="grid h-fit gap-3">
                  <SideFact icon={Sparkles} label="证据引用" value={countEvidenceMentions(selectedReport.content)} />
                  <SideFact icon={FileText} label="正文行数" value={selectedReport.content.split("\n").length} />
                  <SideFact icon={CalendarDays} label="创建时间" value={formatShortDate(selectedReport.createdAt)} />
                  <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
                    <p className="text-sm font-semibold text-[#1D1D1F]">派发状态</p>
                    <p className="mt-2 text-sm leading-6 text-[#86868B]">
                      {selectedReport.status === "sent"
                        ? "报告已进入通知链路，可在站内通知中心追踪。"
                        : "报告已生成，发送后会同步生成站内通知。"}
                    </p>
                  </div>
                </aside>
              </div>
            </div>
          ) : (
            <div className="m-5 rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-8 text-sm text-[#86868B]">
              选择一份报告查看正文
            </div>
          )}
        </section>
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
        <span className={cn("flex h-10 w-10 items-center justify-center rounded-full", toneClasses[tone])}>
          <Icon size={18} aria-hidden="true" />
        </span>
      </div>
      <p className="text-3xl font-semibold tracking-tight text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function ReportMarkdown({ content }: { content: string }) {
  return (
    <div className="grid gap-3 text-sm leading-7 text-[#5F5757]">
      {content.split("\n").map((line, index) => {
        if (line.startsWith("# ")) {
          return (
            <h1 className="text-2xl font-semibold tracking-tight text-[#1D1D1F]" key={`${line}-${index}`}>
              {line.slice(2)}
            </h1>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h2 className="mt-4 text-base font-semibold text-[#1D1D1F]" key={`${line}-${index}`}>
              {line.slice(3)}
            </h2>
          );
        }
        if (line.startsWith("### ")) {
          return (
            <h3 className="mt-2 rounded-xl bg-white px-3 py-2 text-sm font-semibold text-[#C25B6E]" key={`${line}-${index}`}>
              {line.slice(4)}
            </h3>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <p className="rounded-xl bg-white px-3 py-2" key={`${line}-${index}`}>
              {line.slice(2)}
            </p>
          );
        }
        if (/^\d+\.\s/.test(line.trim())) {
          return (
            <p className="rounded-xl border border-[#F4D9DF] bg-[#FFF7F8] px-3 py-2" key={`${line}-${index}`}>
              {renderInline(line.trim())}
            </p>
          );
        }
        if (line.trim().length === 0) {
          return <div className="h-1" key={`blank-${index}`} />;
        }
        return (
          <p className="px-1" key={`${line}-${index}`}>
            {renderInline(line.trim())}
          </p>
        );
      })}
    </div>
  );
}

function SideFact({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FileText;
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold text-[#86868B]">{label}</p>
        <Icon size={16} className="text-[#C25B6E]" aria-hidden="true" />
      </div>
      <p className="mt-2 text-lg font-semibold text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const className =
    status === "sent"
      ? "bg-[#EAF8EE] text-[#2EBA62]"
      : status === "generated"
        ? "bg-[#FFF4DE] text-[#FF9800]"
        : "bg-[#FBF8F5] text-[#86868B]";
  const label = status === "sent" ? "已发送" : status === "generated" ? "待发送" : status;
  return <span className={cn("rounded-lg px-2.5 py-1 text-xs font-semibold", className)}>{label}</span>;
}

function Pill({ children, tone }: { children: ReactNode; tone: "amber" | "green" | "neutral" | "rose" }) {
  const toneClasses = {
    amber: "bg-[#FFF4DE] text-[#FF9800]",
    green: "bg-[#EAF8EE] text-[#2EBA62]",
    neutral: "bg-[#FBF8F5] text-[#86868B]",
    rose: "bg-[#FCEBF0] text-[#C25B6E]",
  };
  return <span className={cn("rounded-full px-3 py-1 text-xs font-semibold", toneClasses[tone])}>{children}</span>;
}

function Tag({ children }: { children: ReactNode }) {
  return <span className="rounded-lg bg-white px-2 py-1">{children}</span>;
}

function renderInline(line: string) {
  const directIntelligenceId = line.match(/^情报 ID：([a-zA-Z0-9_-]+)$/);
  if (directIntelligenceId) {
    const intelligenceId = directIntelligenceId[1];
    return (
      <span>
        情报 ID：
        <Link className="font-semibold text-[#C25B6E]" href={`/intelligence/${intelligenceId}`}>
          {intelligenceId}
        </Link>
      </span>
    );
  }
  const inlineIntelligenceId = line.match(/intelligence_id=([a-zA-Z0-9_-]+)/);
  if (inlineIntelligenceId) {
    const intelligenceId = inlineIntelligenceId[1];
    const [before, after = ""] = line.split(`intelligence_id=${intelligenceId}`);
    return (
      <span>
        {before}
        intelligence_id=
        <Link className="font-semibold text-[#C25B6E]" href={`/intelligence/${intelligenceId}`}>
          {intelligenceId}
        </Link>
        {after}
      </span>
    );
  }
  const parts = line.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong className="font-semibold text-[#1D1D1F]" key={`${part}-${index}`}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

function estimateReadingMinutes(content: string) {
  const words = content.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(words / 180));
}

function countEvidenceMentions(content: string) {
  const matches = content.match(/证据数|evidence/gi);
  return matches?.length ?? 0;
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
