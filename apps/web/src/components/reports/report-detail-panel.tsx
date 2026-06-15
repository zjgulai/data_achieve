"use client";

import {
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Copy,
  Download,
  ExternalLink,
  FileText,
  History,
  Link2,
  Send,
  Share2,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  createReportAuditEvent,
  listReportAuditEvents,
  listReportEvidenceReferences,
} from "@/lib/api/reports";
import { cn } from "@/lib/utils";
import type { Evidence } from "@/types/intelligence";
import type {
  Report,
  ReportAuditEvent,
  ReportEvidenceReference,
} from "@/types/report";

type ReportSection = {
  id: string;
  level: 1 | 2;
  title: string;
  lines: string[];
};

type ReportDetailPanelProps = {
  busy?: boolean;
  onSend: (report: Report) => Promise<void> | void;
  report: Report;
  showOpenLink?: boolean;
};

export function ReportDetailPanel({
  busy = false,
  onSend,
  report,
  showOpenLink = false,
}: ReportDetailPanelProps) {
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceReferences, setEvidenceReferences] = useState<
    ReportEvidenceReference[]
  >([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditEvents, setAuditEvents] = useState<ReportAuditEvent[]>([]);
  const [openSectionIds, setOpenSectionIds] = useState<Set<string>>(new Set());
  const [shareNotice, setShareNotice] = useState<string | null>(null);

  const reportUrl = useMemo(() => {
    if (typeof window === "undefined") {
      return `/reports/${report.id}`;
    }
    return new URL(`/reports/${report.id}`, window.location.origin).toString();
  }, [report.id]);

  const loadAuditEvents = useCallback(async () => {
    setAuditLoading(true);
    try {
      setAuditEvents(await listReportAuditEvents(report.id));
    } catch {
      setAuditEvents([]);
    } finally {
      setAuditLoading(false);
    }
  }, [report.id]);

  useEffect(() => {
    const sections = parseReportSections(report.content);
    setOpenSectionIds(new Set(sections.map((section) => section.id)));

    let mounted = true;
    setEvidenceLoading(true);
    listReportEvidenceReferences(report.id)
      .then((items) => {
        if (mounted) {
          setEvidenceReferences(items);
        }
      })
      .catch(() => {
        if (mounted) {
          setEvidenceReferences([]);
        }
      })
      .finally(() => {
        if (mounted) {
          setEvidenceLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [report.content, report.id]);

  useEffect(() => {
    void loadAuditEvents();
  }, [loadAuditEvents]);

  const reportSections = useMemo(
    () => parseReportSections(report.content),
    [report.content],
  );
  const evidenceReferenceCount = useMemo(
    () =>
      evidenceReferences.reduce(
        (total, reference) => total + reference.evidences.length,
        0,
      ),
    [evidenceReferences],
  );

  function toggleSection(sectionId: string) {
    setOpenSectionIds((current) => {
      const next = new Set(current);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  }

  async function handleCopyLink() {
    setShareNotice(null);
    await copyTextToClipboard(reportUrl);
    await createReportAuditEvent(report.id, "share_link_copied", {
      url: reportUrl,
    });
    await loadAuditEvents();
    setShareNotice("链接已复制");
  }

  async function handleShareLink() {
    setShareNotice(null);
    if (navigator.share) {
      await navigator.share({ title: report.title, url: reportUrl });
      await createReportAuditEvent(report.id, "share_sheet_opened", {
        url: reportUrl,
      });
      setShareNotice("分享面板已打开");
    } else {
      await copyTextToClipboard(reportUrl);
      await createReportAuditEvent(report.id, "share_link_copied", {
        fallback: "web_share_unavailable",
        url: reportUrl,
      });
      setShareNotice("链接已复制");
    }
    await loadAuditEvents();
  }

  async function handleSendClick() {
    await onSend(report);
    await loadAuditEvents();
  }

  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-[#E9E5E2] bg-white">
      <div className="border-b border-[#EDE6DF] p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <StatusPill status={report.status} />
              <Pill tone="neutral">{report.reportType}</Pill>
              <Pill tone="rose">
                {estimateReadingMinutes(report.content)} min read
              </Pill>
            </div>
            <h2 className="break-words text-xl font-semibold tracking-tight text-[#1D1D1F] [overflow-wrap:anywhere]">
              {report.title}
            </h2>
            <p className="mt-2 text-sm text-[#86868B]">
              {formatDate(report.periodStart)} 至 {formatDate(report.periodEnd)}
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap gap-2">
            {showOpenLink ? (
              <Link
                className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-4 text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] sm:w-auto"
                href={`/reports/${report.id}` as Route}
              >
                <FileText size={16} aria-hidden="true" />
                打开详情页
              </Link>
            ) : null}
            <button
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-4 text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] sm:w-auto"
              onClick={() => void handleCopyLink()}
              type="button"
            >
              <Copy size={16} aria-hidden="true" />
              复制链接
            </button>
            <button
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-4 text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] sm:w-auto"
              onClick={() => void handleShareLink()}
              type="button"
            >
              <Share2 size={16} aria-hidden="true" />
              分享
            </button>
            <button
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-4 text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] sm:w-auto"
              onClick={() => downloadReportMarkdown(report)}
              type="button"
            >
              <Download size={16} aria-hidden="true" />
              下载 Markdown
            </button>
            <button
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-4 text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
              disabled={busy || report.status === "sent"}
              onClick={() => void handleSendClick()}
              type="button"
            >
              {report.status === "sent" ? (
                <CheckCircle2 size={16} aria-hidden="true" />
              ) : (
                <Send size={16} aria-hidden="true" />
              )}
              {report.status === "sent" ? "已发送" : "发送报告"}
            </button>
          </div>
        </div>
        {shareNotice ? (
          <p className="mt-3 inline-flex items-center gap-2 rounded-xl bg-[#EAF8EE] px-3 py-2 text-xs font-semibold text-[#2EBA62]">
            <CheckCircle2 size={14} aria-hidden="true" />
            {shareNotice}
          </p>
        ) : null}
      </div>

      <div className="grid min-w-0 gap-5 p-4 sm:p-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <article className="min-w-0 overflow-hidden rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
          <SectionedReportMarkdown
            onToggle={toggleSection}
            openSectionIds={openSectionIds}
            sections={reportSections}
          />
        </article>

        <aside className="grid min-w-0 gap-3 xl:sticky xl:top-24 xl:max-h-[calc(100vh-7rem)] xl:overflow-y-auto xl:pr-1">
          <SideFact
            icon={Sparkles}
            label="证据引用"
            value={evidenceReferenceCount}
          />
          <SideFact
            icon={FileText}
            label="正文行数"
            value={report.content.split("\n").length}
          />
          <SideFact
            icon={CalendarDays}
            label="创建时间"
            value={formatShortDate(report.createdAt)}
          />
          <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
            <p className="text-sm font-semibold text-[#1D1D1F]">派发状态</p>
            <p className="mt-2 text-sm leading-6 text-[#86868B]">
              {report.status === "sent"
                ? "报告已进入通知链路，可在站内通知中心追踪。"
                : "报告已生成，发送后会同步生成站内通知。"}
            </p>
          </div>
          <ReportAuditTimeline events={auditEvents} loading={auditLoading} />
          <EvidenceReferencesPanel
            loading={evidenceLoading}
            references={evidenceReferences}
          />
        </aside>
      </div>
    </section>
  );
}

function ReportAuditTimeline({
  events,
  loading,
}: {
  events: ReportAuditEvent[];
  loading: boolean;
}) {
  return (
    <div className="min-w-0 overflow-hidden rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
      <div className="mb-3 flex min-w-0 items-center justify-between gap-3">
        <p className="text-sm font-semibold text-[#1D1D1F]">审计记录</p>
        <History size={16} className="text-[#C25B6E]" aria-hidden="true" />
      </div>
      {loading ? (
        <p className="text-sm text-[#86868B]">加载审计记录中</p>
      ) : null}
      {!loading && events.length === 0 ? (
        <p className="text-sm leading-6 text-[#86868B]">暂无审计记录</p>
      ) : null}
      <div className="grid gap-2">
        {events.map((event) => (
          <div className="min-w-0 rounded-xl bg-white px-3 py-2" key={event.id}>
            <div className="flex min-w-0 items-center justify-between gap-3">
              <p className="min-w-0 break-words text-xs font-semibold text-[#1D1D1F] [overflow-wrap:anywhere]">
                {auditEventLabel(event.eventType)}
              </p>
              <span className="text-[11px] text-[#86868B]">
                {formatShortDateTime(event.createdAt)}
              </span>
            </div>
            <p className="mt-1 text-xs leading-5 text-[#86868B]">
              {event.fromStatus &&
              event.toStatus &&
              event.fromStatus !== event.toStatus
                ? `${statusLabel(event.fromStatus)} → ${statusLabel(event.toStatus)}`
                : statusLabel(
                    event.toStatus ?? event.fromStatus ?? "generated",
                  )}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function SectionedReportMarkdown({
  onToggle,
  openSectionIds,
  sections,
}: {
  onToggle: (sectionId: string) => void;
  openSectionIds: Set<string>;
  sections: ReportSection[];
}) {
  return (
    <div className="grid min-w-0 gap-3">
      {sections.map((section) => {
        const open = openSectionIds.has(section.id);
        return (
          <section
            className="min-w-0 overflow-hidden rounded-xl border border-[#EDE6DF] bg-white"
            key={section.id}
          >
            <button
              aria-expanded={open}
              aria-label={open ? "收起章节" : "展开章节"}
              className="flex w-full min-w-0 items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-[#FFF7F8]"
              onClick={() => onToggle(section.id)}
              type="button"
            >
              <span className="min-w-0">
                <span
                  role="heading"
                  aria-level={section.level}
                  className={cn(
                    "block break-words font-semibold tracking-tight text-[#1D1D1F] [overflow-wrap:anywhere]",
                    section.level === 1 ? "text-lg" : "text-base",
                  )}
                >
                  {section.title}
                </span>
                <span className="mt-1 block text-xs text-[#86868B]">
                  {
                    section.lines.filter((line) => line.trim().length > 0)
                      .length
                  }{" "}
                  行
                </span>
              </span>
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#FBF8F5] text-[#C25B6E]">
                <ChevronDown
                  className={cn(
                    "transition-transform",
                    open ? "rotate-180" : "rotate-0",
                  )}
                  size={16}
                  aria-hidden="true"
                />
              </span>
            </button>
            {open ? (
              <div className="min-w-0 border-t border-[#EDE6DF] bg-[#FBF8F5] px-4 py-4">
                <ReportMarkdownLines lines={section.lines} />
              </div>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}

function ReportMarkdownLines({ lines }: { lines: string[] }) {
  return (
    <div className="grid min-w-0 gap-3 text-sm leading-7 text-[#5F5757]">
      {lines.map((line, index) => {
        if (line.startsWith("# ")) {
          return (
            <h1
              className="break-words text-2xl font-semibold tracking-tight text-[#1D1D1F] [overflow-wrap:anywhere]"
              key={`${line}-${index}`}
            >
              {line.slice(2)}
            </h1>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h2
              className="mt-4 break-words text-base font-semibold text-[#1D1D1F] [overflow-wrap:anywhere]"
              key={`${line}-${index}`}
            >
              {line.slice(3)}
            </h2>
          );
        }
        if (line.startsWith("### ")) {
          return (
            <h3
              className="mt-2 min-w-0 break-words rounded-xl bg-white px-3 py-2 text-sm font-semibold text-[#C25B6E] [overflow-wrap:anywhere]"
              key={`${line}-${index}`}
            >
              {line.slice(4)}
            </h3>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <p
              className="min-w-0 break-words rounded-xl bg-white px-3 py-2 [overflow-wrap:anywhere]"
              key={`${line}-${index}`}
            >
              {line.slice(2)}
            </p>
          );
        }
        if (/^\d+\.\s/.test(line.trim())) {
          return (
            <p
              className="min-w-0 break-words rounded-xl border border-[#F4D9DF] bg-[#FFF7F8] px-3 py-2 [overflow-wrap:anywhere]"
              key={`${line}-${index}`}
            >
              {renderInline(line.trim())}
            </p>
          );
        }
        if (line.trim().length === 0) {
          return <div className="h-1" key={`blank-${index}`} />;
        }
        return (
          <p
            className="min-w-0 break-words px-1 [overflow-wrap:anywhere]"
            key={`${line}-${index}`}
          >
            {renderInline(line.trim())}
          </p>
        );
      })}
    </div>
  );
}

function EvidenceReferencesPanel({
  loading,
  references,
}: {
  loading: boolean;
  references: ReportEvidenceReference[];
}) {
  return (
    <div className="min-w-0 overflow-hidden rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
      <div className="mb-3 flex min-w-0 items-center justify-between gap-3">
        <p className="min-w-0 break-words text-sm font-semibold text-[#1D1D1F] [overflow-wrap:anywhere]">
          证据引用详情
        </p>
        <Link2 size={16} className="text-[#C25B6E]" aria-hidden="true" />
      </div>
      {loading ? (
        <p className="text-sm text-[#86868B]">加载证据引用中</p>
      ) : null}
      {!loading && references.length === 0 ? (
        <p className="text-sm leading-6 text-[#86868B]">
          当前报告周期没有可追溯情报
        </p>
      ) : null}
      <div className="grid min-w-0 gap-3">
        {references.map((reference) => (
          <div
            className="min-w-0 overflow-hidden rounded-xl border border-[#EDE6DF] bg-white p-3"
            key={reference.intelligence.id}
          >
            <div className="flex min-w-0 items-start justify-between gap-3">
              <Link
                className="min-w-0 break-words text-sm font-semibold leading-5 text-[#1D1D1F] transition-colors [overflow-wrap:anywhere] hover:text-[#C25B6E]"
                href={`/intelligence/${reference.intelligence.id}`}
              >
                {reference.intelligence.title}
              </Link>
              <span className="shrink-0 rounded-lg bg-[#FCEBF0] px-2 py-1 text-xs font-semibold text-[#C25B6E]">
                {reference.evidences.length}
              </span>
            </div>
            <p className="mt-1 break-words text-xs text-[#86868B] [overflow-wrap:anywhere]">
              {reference.intelligence.domain} · Score{" "}
              {reference.intelligence.finalScore.toFixed(1)}
            </p>
            <div className="mt-3 grid min-w-0 gap-2">
              {reference.evidences.slice(0, 3).map((evidence) => (
                <EvidenceReferenceRow evidence={evidence} key={evidence.id} />
              ))}
            </div>
            {reference.evidences.length > 3 ? (
              <p className="mt-2 text-xs text-[#86868B]">
                另有 {reference.evidences.length - 3} 条证据
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceReferenceRow({ evidence }: { evidence: Evidence }) {
  const sourceName =
    evidence.source?.name ?? evidence.entity?.name ?? evidence.evidenceType;
  return (
    <div className="min-w-0 overflow-hidden rounded-lg bg-[#FBF8F5] px-3 py-2">
      <div className="flex min-w-0 items-center justify-between gap-2">
        <p className="min-w-0 break-words text-xs font-semibold text-[#5F5757] [overflow-wrap:anywhere]">
          {evidence.title}
        </p>
        <span className="shrink-0 rounded-md bg-white px-1.5 py-0.5 text-[11px] font-semibold text-[#86868B]">
          {evidence.evidenceType}
        </span>
      </div>
      <p className="mt-1 min-w-0 break-words text-xs text-[#86868B] [overflow-wrap:anywhere]">
        {sourceName}
      </p>
      {evidence.rawRecord ? (
        <p className="mt-1 min-w-0 break-words text-[11px] text-[#86868B] [overflow-wrap:anywhere]">
          Raw {shortId(evidence.rawRecord.id)} ·{" "}
          {evidence.rawRecord.contentHash.slice(0, 10)}
        </p>
      ) : null}
      {(evidence.url ??
      evidence.rawRecord?.sourceUrl ??
      evidence.source?.url) ? (
        <a
          className="mt-2 inline-flex max-w-full min-w-0 items-center gap-1 break-words text-xs font-semibold text-[#C25B6E] [overflow-wrap:anywhere]"
          href={
            evidence.url ??
            evidence.rawRecord?.sourceUrl ??
            evidence.source?.url ??
            undefined
          }
          rel="noreferrer"
          target="_blank"
        >
          <ExternalLink size={12} aria-hidden="true" />
          <span className="min-w-0">打开来源</span>
        </a>
      ) : null}
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
    <div className="min-w-0 overflow-hidden rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
      <div className="flex min-w-0 items-center justify-between gap-3">
        <p className="min-w-0 break-words text-xs font-semibold text-[#86868B] [overflow-wrap:anywhere]">
          {label}
        </p>
        <Icon size={16} className="text-[#C25B6E]" aria-hidden="true" />
      </div>
      <p className="mt-2 break-words text-lg font-semibold text-[#1D1D1F] [overflow-wrap:anywhere]">
        {value}
      </p>
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
  const label =
    status === "sent" ? "已发送" : status === "generated" ? "待发送" : status;
  return (
    <span
      className={cn("rounded-lg px-2.5 py-1 text-xs font-semibold", className)}
    >
      {label}
    </span>
  );
}

function Pill({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "neutral" | "rose";
}) {
  const toneClasses = {
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

function parseReportSections(content: string): ReportSection[] {
  const sections: ReportSection[] = [];
  const seenSlugs = new Map<string, number>();
  let current: ReportSection | null = null;

  function pushCurrent() {
    if (current && current.lines.some((line) => line.trim().length > 0)) {
      sections.push(current);
    }
  }

  for (const line of content.split("\n")) {
    const heading = line.match(/^(#{1,2})\s+(.+)$/);
    if (heading) {
      pushCurrent();
      const title = heading[2].trim();
      const baseSlug = slugify(title) || `section-${sections.length + 1}`;
      const nextCount = (seenSlugs.get(baseSlug) ?? 0) + 1;
      seenSlugs.set(baseSlug, nextCount);
      current = {
        id: `${baseSlug}-${nextCount}`,
        level: heading[1].length as 1 | 2,
        title,
        lines: [],
      };
      continue;
    }

    if (!current) {
      current = {
        id: "report-body-1",
        level: 2,
        title: "正文",
        lines: [],
      };
    }
    current.lines.push(line);
  }

  pushCurrent();
  return sections;
}

function downloadReportMarkdown(report: Report) {
  const blob = new Blob([report.content], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeFilename(report.title)}.md`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function safeFilename(value: string) {
  const filename = value
    .trim()
    .replace(/[^\w\u4e00-\u9fa5-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return filename || "report";
}

function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fa5-]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function renderInline(line: string) {
  const directIntelligenceId = line.match(/^情报 ID：([a-zA-Z0-9_-]+)$/);
  if (directIntelligenceId) {
    const intelligenceId = directIntelligenceId[1];
    return (
      <span>
        情报 ID：
        <Link
          className="break-all font-semibold text-[#C25B6E]"
          href={`/intelligence/${intelligenceId}`}
        >
          {intelligenceId}
        </Link>
      </span>
    );
  }
  const inlineIntelligenceId = line.match(/intelligence_id=([a-zA-Z0-9_-]+)/);
  if (inlineIntelligenceId) {
    const intelligenceId = inlineIntelligenceId[1];
    const [before, after = ""] = line.split(
      `intelligence_id=${intelligenceId}`,
    );
    return (
      <span>
        {before}
        intelligence_id=
        <Link
          className="break-all font-semibold text-[#C25B6E]"
          href={`/intelligence/${intelligenceId}`}
        >
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
        <strong
          className="font-semibold text-[#1D1D1F]"
          key={`${part}-${index}`}
        >
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

function shortId(value: string) {
  return value.slice(0, 8);
}

function estimateReadingMinutes(content: string) {
  const words = content.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(words / 180));
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

function formatShortDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function auditEventLabel(eventType: string) {
  const labels: Record<string, string> = {
    generated: "报告生成",
    send_skipped: "渠道跳过",
    sent: "报告发送",
    share_link_copied: "复制链接",
    share_sheet_opened: "系统分享",
    subscription_executed: "订阅自动派发",
  };
  return labels[eventType] ?? eventType;
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    generated: "待发送",
    sent: "已发送",
  };
  return labels[status] ?? status;
}

async function copyTextToClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // Fall through to the legacy copy path when browser permissions block Clipboard API.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}
