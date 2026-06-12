"use client";

import {
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  FileSearch,
  MessageSquare,
  RadioTower,
  ShieldCheck,
  SplitSquareHorizontal,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  getIntelligence,
  listEvidences,
  submitFeedback,
  updateIntelligenceStatus,
} from "@/lib/api/intelligence";
import { getSignalSnapshotCompare } from "@/lib/api/signals";
import type {
  Evidence,
  FeedbackType,
  IntelligenceItem,
  IntelligenceStatus,
} from "@/types/intelligence";
import type { SignalSnapshotCompare } from "@/types/signal";

const statusClass: Record<string, string> = {
  new: "bg-[#ecfeff] text-[#0e7490]",
  reviewed: "bg-[#eef2ff] text-[#4338ca]",
  following: "bg-[#ecfdf5] text-[#047857]",
  dismissed: "bg-[#f1f5f9] text-[#475569]",
  converted: "bg-[#fef3c7] text-[#92400e]",
};

const typeClass: Record<string, string> = {
  trend: "bg-[#ecfdf5] text-[#047857]",
  risk: "bg-[#fee2e2] text-[#b91c1c]",
  competitor: "bg-[#eff6ff] text-[#1d4ed8]",
  opportunity: "bg-[#fef3c7] text-[#92400e]",
  anomaly: "bg-[#f1f5f9] text-[#475569]",
};

export function IntelligenceDetailWorkspace({ intelligenceId }: { intelligenceId: string }) {
  const [item, setItem] = useState<IntelligenceItem | null>(null);
  const [evidences, setEvidences] = useState<Evidence[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [snapshotCompare, setSnapshotCompare] = useState<SignalSnapshotCompare | null>(null);
  const [loading, setLoading] = useState(true);
  const [compareLoading, setCompareLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedbackState, setFeedbackState] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    Promise.all([getIntelligence(intelligenceId), listEvidences(intelligenceId)])
      .then(([intelligence, evidenceItems]) => {
        if (!mounted) {
          return;
        }
        setItem(intelligence);
        setEvidences(evidenceItems);
        setSelectedEvidenceId(evidenceItems[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load intelligence");
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
  }, [intelligenceId]);

  const selectedEvidence = useMemo(() => {
    return evidences.find((evidence) => evidence.id === selectedEvidenceId) ?? null;
  }, [evidences, selectedEvidenceId]);

  useEffect(() => {
    if (!selectedEvidence?.signalId) {
      setSnapshotCompare(null);
      return;
    }
    let mounted = true;
    setCompareLoading(true);
    getSignalSnapshotCompare(selectedEvidence.signalId)
      .then((compare) => {
        if (mounted) {
          setSnapshotCompare(compare);
        }
      })
      .catch(() => {
        if (mounted) {
          setSnapshotCompare(null);
        }
      })
      .finally(() => {
        if (mounted) {
          setCompareLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [selectedEvidence?.signalId]);

  async function handleStatusChange(status: IntelligenceStatus) {
    if (!item) {
      return;
    }
    const updated = await updateIntelligenceStatus(item.id, status);
    setItem(updated);
  }

  async function handleFeedback(feedbackType: FeedbackType) {
    if (!item) {
      return;
    }
    const feedback = await submitFeedback(item.id, feedbackType);
    setFeedbackState(feedback.feedbackType);
  }

  if (loading) {
    return <p className="text-sm text-[#6b7280]">加载情报中</p>;
  }

  if (error || !item) {
    return (
      <div className="rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
        {error ?? "Intelligence item not found"}
      </div>
    );
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_430px]">
      <section className="grid gap-5">
        <div className="rounded-lg border border-[#dfe3ea] bg-white p-5">
          <Link
            className="mb-4 inline-flex items-center gap-2 text-sm font-semibold text-[#0f766e]"
            href="/intelligence"
          >
            <ArrowLeft size={16} aria-hidden="true" />
            情报列表
          </Link>
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold leading-8">{item.title}</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                <Tag className={typeClass[item.intelligenceType]} label={item.intelligenceType} />
                <Tag className={statusClass[item.status]} label={item.status} />
                <Tag className="bg-[#f1f5f9] text-[#475569]" label={item.domain} />
                <Tag
                  className="bg-[#f7f8fa] text-[#374151]"
                  label={`${item.evidenceCount} evidences`}
                />
              </div>
            </div>
            <ScoreBadge score={item.finalScore} />
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            <ScoreBar label="Impact" value={item.impactScore} />
            <ScoreBar label="Confidence" value={item.confidenceScore} />
            <ScoreBar label="Novelty" value={item.noveltyScore} />
            <ScoreBar label="Urgency" value={item.urgencyScore} />
          </div>
        </div>

        <div className="rounded-lg border border-[#dfe3ea] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">AI Summary</h2>
            <FileSearch size={18} className="text-[#6b7280]" aria-hidden="true" />
          </div>
          <div className="grid gap-2">
            {summaryClaims(item.summary).map((claim, index) => {
              const evidence = evidences[index % Math.max(evidences.length, 1)] ?? null;
              const selected = evidence?.id === selectedEvidenceId;
              return (
                <button
                  className={`rounded-md border px-3 py-3 text-left text-sm leading-6 transition ${
                    selected
                      ? "border-[#0f766e] bg-[#ecfdf5] text-[#064e3b]"
                      : "border-[#dfe3ea] bg-white text-[#374151] hover:border-[#94a3b8]"
                  }`}
                  disabled={!evidence}
                  key={claim}
                  onClick={() => evidence && setSelectedEvidenceId(evidence.id)}
                  type="button"
                >
                  {claim}
                </button>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border border-[#dfe3ea] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Snapshot Compare</h2>
            <SplitSquareHorizontal size={18} className="text-[#6b7280]" aria-hidden="true" />
          </div>
          {compareLoading ? <p className="text-sm text-[#6b7280]">加载对比中</p> : null}
          {snapshotCompare ? (
            <SnapshotComparePanel compare={snapshotCompare} />
          ) : (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-5 text-sm text-[#6b7280]">
              当前证据暂无快照对比
            </div>
          )}
        </div>
      </section>

      <aside className="grid gap-5">
        <div className="rounded-lg border border-[#dfe3ea] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">Evidence Timeline</h2>
            <RadioTower size={18} className="text-[#6b7280]" aria-hidden="true" />
          </div>
          <div className="grid gap-2">
            {evidences.map((evidence) => (
              <button
                className={`rounded-md border px-3 py-3 text-left transition ${
                  evidence.id === selectedEvidenceId
                    ? "border-[#0f766e] bg-[#ecfdf5]"
                    : "border-[#dfe3ea] bg-white hover:border-[#94a3b8]"
                }`}
                key={evidence.id}
                onClick={() => setSelectedEvidenceId(evidence.id)}
                type="button"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold">{evidence.title}</p>
                    <p className="mt-1 text-xs text-[#6b7280]">{evidence.evidenceType}</p>
                  </div>
                  <span className="text-xs text-[#6b7280]">
                    {new Date(evidence.createdAt).toLocaleString()}
                  </span>
                </div>
                {evidence.excerpt ? (
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#6b7280]">
                    {evidence.excerpt}
                  </p>
                ) : null}
              </button>
            ))}
          </div>
        </div>

        <AuditDrawer evidence={selectedEvidence} />

        <div className="rounded-lg border border-[#dfe3ea] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold">状态与反馈</h2>
            <ShieldCheck size={18} className="text-[#6b7280]" aria-hidden="true" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            {(["reviewed", "following", "dismissed", "converted"] as IntelligenceStatus[]).map(
              (status) => (
                <button
                  className={`rounded-md border px-3 py-2 text-xs font-semibold transition ${
                    item.status === status
                      ? "border-[#0f766e] bg-[#ecfdf5] text-[#047857]"
                      : "border-[#dfe3ea] bg-white text-[#374151] hover:border-[#94a3b8]"
                  }`}
                  key={status}
                  onClick={() => void handleStatusChange(status)}
                  type="button"
                >
                  {status}
                </button>
              ),
            )}
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <FeedbackButton
              icon={CheckCircle2}
              label="有用"
              onClick={() => void handleFeedback("useful")}
            />
            <FeedbackButton
              icon={XCircle}
              label="无用"
              onClick={() => void handleFeedback("not_useful")}
            />
            <FeedbackButton
              icon={MessageSquare}
              label="误报"
              onClick={() => void handleFeedback("false_positive")}
            />
          </div>
          {feedbackState ? (
            <p className="mt-3 rounded-md bg-[#f7f8fa] px-3 py-2 text-xs text-[#475569]">
              已提交：{feedbackState}
            </p>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

function summaryClaims(summary: string) {
  const claims = summary
    .split(/(?<=\.)\s+/)
    .map((claim) => claim.trim())
    .filter(Boolean);
  return claims.length > 0 ? claims : [summary];
}

function SnapshotComparePanel({ compare }: { compare: SignalSnapshotCompare }) {
  return (
    <div className="grid gap-4">
      <div className="grid gap-3 md:grid-cols-2">
        <SnapshotBox label="Old Snapshot" value={compare.previousSnapshot} />
        <SnapshotBox label="New Snapshot" value={compare.currentSnapshot} />
      </div>
      <div className="overflow-hidden rounded-md border border-[#dfe3ea]">
        <div className="grid grid-cols-[1fr_1fr_1fr_1fr] bg-[#f7f8fa] px-3 py-2 text-xs font-semibold text-[#475569]">
          <span>Metric</span>
          <span>Old</span>
          <span>New</span>
          <span>Delta</span>
        </div>
        {compare.metricsDiff.map((item) => (
          <div
            className="grid grid-cols-[1fr_1fr_1fr_1fr] border-t border-[#edf0f4] px-3 py-2 text-xs"
            key={item.metric}
          >
            <span className="font-semibold">{item.metric}</span>
            <span className="break-all text-[#6b7280]">{formatValue(item.previousValue)}</span>
            <span className="break-all text-[#111827]">{formatValue(item.currentValue)}</span>
            <span>{item.delta === null ? "n/a" : item.delta.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SnapshotBox({
  label,
  value,
}: {
  label: string;
  value: SignalSnapshotCompare["previousSnapshot"];
}) {
  return (
    <div className="rounded-md border border-[#dfe3ea] p-4">
      <p className="text-xs font-semibold uppercase text-[#6b7280]">{label}</p>
      <p className="mt-2 break-all text-sm font-semibold">{value.id}</p>
      <p className="mt-1 text-xs text-[#6b7280]">{new Date(value.capturedAt).toLocaleString()}</p>
      <pre className="mt-3 max-h-52 overflow-auto rounded-md bg-[#111827] p-3 text-xs leading-5 text-[#e5e7eb]">
        {JSON.stringify(value.metrics, null, 2)}
      </pre>
    </div>
  );
}

function AuditDrawer({ evidence }: { evidence: Evidence | null }) {
  return (
    <div className="rounded-lg border border-[#dfe3ea] bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold">审计抽屉</h2>
        <FileSearch size={18} className="text-[#6b7280]" aria-hidden="true" />
      </div>
      {evidence ? (
        <div className="grid gap-3">
          <DetailRow label="Evidence ID" value={evidence.id} />
          {evidence.signalId ? <DetailRow label="Signal ID" value={evidence.signalId} /> : null}
          {evidence.rawRecordId ? (
            <DetailRow label="RawRecord ID" value={evidence.rawRecordId} />
          ) : null}
          {evidence.url ? (
            <a
              className="inline-flex items-center gap-2 break-all rounded-md border border-[#dfe3ea] px-3 py-2 text-sm text-[#0f766e]"
              href={evidence.url}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink size={15} aria-hidden="true" />
              {evidence.url}
            </a>
          ) : null}
          {evidence.screenshotUrl ? (
            <img
              alt={evidence.title}
              className="max-h-64 w-full rounded-md border border-[#dfe3ea] object-cover"
              src={evidence.screenshotUrl}
            />
          ) : null}
          <pre className="max-h-72 overflow-auto rounded-md bg-[#111827] p-3 text-xs leading-5 text-[#e5e7eb]">
            {evidence.highlightedText ?? evidence.excerpt ?? "No highlighted text"}
          </pre>
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-[#dfe3ea] p-5 text-sm text-[#6b7280]">
          暂无选中证据
        </p>
      )}
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <div className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-md bg-[#111827] text-white">
      <span className="text-lg font-semibold">{score.toFixed(0)}</span>
      <span className="text-[10px] uppercase text-[#d1d5db]">score</span>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-semibold text-[#374151]">{label}</span>
        <span className="text-[#6b7280]">{value.toFixed(1)}</span>
      </div>
      <div className="h-2 rounded-full bg-[#e5e7eb]">
        <div
          className="h-2 rounded-full bg-[#0f766e]"
          style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
        />
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-[#f7f8fa] px-3 py-2 text-sm">
      <span className="text-[#6b7280]">{label}</span>
      <p className="mt-1 break-all font-medium">{value}</p>
    </div>
  );
}

function FeedbackButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof CheckCircle2;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className="flex items-center justify-center gap-2 rounded-md border border-[#dfe3ea] px-3 py-2 text-xs font-semibold text-[#374151] hover:border-[#94a3b8]"
      onClick={onClick}
      type="button"
    >
      <Icon size={15} aria-hidden="true" />
      {label}
    </button>
  );
}

function Tag({ className, label }: { className?: string; label: string }) {
  return (
    <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ${className ?? ""}`}>
      {label}
    </span>
  );
}

function formatValue(value: unknown) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  if (typeof value === "number") {
    return value.toFixed(2);
  }
  return String(value);
}
