"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ReportDetailPanel } from "@/components/reports/report-detail-panel";
import { getReport, sendReport } from "@/lib/api/reports";
import type { Report } from "@/types/report";

export function ReportDetailPageWorkspace({ reportId }: { reportId: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    getReport(reportId)
      .then((item) => {
        if (mounted) {
          setReport(item);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load report");
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
  }, [reportId]);

  async function handleSend(current: Report) {
    setBusy(true);
    setError(null);
    try {
      const sent = await sendReport(current.id);
      setReport(sent);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Report send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-w-0 gap-5">
      <div>
        <Link
          className="inline-flex h-10 items-center rounded-xl border border-[#EDE6DF] bg-white px-4 text-sm font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]"
          href="/reports"
        >
          返回报告中心
        </Link>
      </div>
      {error ? (
        <p className="rounded-2xl border border-[#FFD7DF] bg-[#FFF7F8] px-4 py-3 text-sm text-[#C25B6E]">
          {error}
        </p>
      ) : null}
      {loading ? (
        <div className="rounded-2xl border border-[#EDE6DF] bg-white p-8 text-sm text-[#86868B]">
          加载报告中
        </div>
      ) : null}
      {report ? <ReportDetailPanel busy={busy} onSend={handleSend} report={report} /> : null}
    </div>
  );
}
