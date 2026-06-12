"use client";

import { FileText, PlusCircle, Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { generateReport, listReports, sendReport } from "@/lib/api/reports";
import type { Report } from "@/types/report";

export function ReportsWorkspace() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const selectedReport = useMemo(
    () => reports.find((report) => report.id === selectedId) ?? null,
    [reports, selectedId],
  );

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      const report = await generateReport({ reportType: "daily" });
      setReports((current) => [report, ...current.filter((item) => item.id !== report.id)]);
      setSelectedId(report.id);
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Report send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">报告列表</h2>
            <p className="mt-1 text-sm text-[#6b7280]">Daily Report · Markdown</p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-md bg-[#0f766e] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
            disabled={busy}
            onClick={() => void handleGenerate()}
            type="button"
          >
            <PlusCircle size={16} aria-hidden="true" />
            Generate
          </button>
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载报告中</p> : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {reports.map((report) => (
            <button
              className={`rounded-md border p-4 text-left transition ${
                report.id === selectedId
                  ? "border-[#0f766e] bg-[#ecfdf5]"
                  : "border-[#dfe3ea] bg-white hover:border-[#94a3b8]"
              }`}
              key={report.id}
              onClick={() => setSelectedId(report.id)}
              type="button"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold leading-6">{report.title}</h3>
                  <p className="mt-1 text-xs text-[#6b7280]">
                    {formatDate(report.periodStart)} 至 {formatDate(report.periodEnd)}
                  </p>
                </div>
                <StatusPill status={report.status} />
              </div>
            </button>
          ))}
          {!loading && reports.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无报告
            </div>
          ) : null}
        </div>
      </section>

      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">报告正文</h2>
            <p className="mt-1 text-sm text-[#6b7280]">生成内容保留情报 ID 和证据数量</p>
          </div>
          <FileText size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {selectedReport ? (
          <div className="grid gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill status={selectedReport.status} />
              <span className="rounded-md bg-[#f7f8fa] px-2.5 py-1 text-xs text-[#475569]">
                {selectedReport.reportType}
              </span>
              <button
                className="ml-auto inline-flex items-center gap-2 rounded-md border border-[#dfe3ea] px-3 py-2 text-sm font-semibold text-[#111827] disabled:opacity-60"
                disabled={busy || selectedReport.status === "sent"}
                onClick={() => void handleSend(selectedReport)}
                type="button"
              >
                <Send size={16} aria-hidden="true" />
                Send
              </button>
            </div>
            <pre className="max-h-[680px] overflow-auto whitespace-pre-wrap rounded-md border border-[#dfe3ea] bg-[#f8fafc] p-4 font-mono text-sm leading-6 text-[#111827]">
              {selectedReport.content}
            </pre>
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
            选择一份报告查看正文
          </div>
        )}
      </section>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const className =
    status === "sent"
      ? "bg-[#ecfdf5] text-[#047857]"
      : "bg-[#fef3c7] text-[#92400e]";
  return <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ${className}`}>{status}</span>;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
