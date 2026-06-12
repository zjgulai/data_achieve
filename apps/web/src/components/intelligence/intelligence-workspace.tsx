"use client";

import {
  CheckCircle2,
  FileSearch,
  ListFilter,
  MessageSquare,
  RadioTower,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  listEvidences,
  listIntelligence,
  submitFeedback,
  updateIntelligenceStatus,
} from "@/lib/api/intelligence";
import type {
  Evidence,
  FeedbackType,
  IntelligenceItem,
  IntelligenceStatus,
} from "@/types/intelligence";

const typeOptions = [
  { value: "", label: "全部类型" },
  { value: "trend", label: "trend" },
  { value: "risk", label: "risk" },
  { value: "competitor", label: "competitor" },
  { value: "opportunity", label: "opportunity" },
  { value: "anomaly", label: "anomaly" },
];

const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "new", label: "new" },
  { value: "reviewed", label: "reviewed" },
  { value: "following", label: "following" },
  { value: "dismissed", label: "dismissed" },
  { value: "converted", label: "converted" },
];

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

export function IntelligenceWorkspace() {
  const [items, setItems] = useState<IntelligenceItem[]>([]);
  const [evidences, setEvidences] = useState<Evidence[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedbackState, setFeedbackState] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    listIntelligence({
      type: typeFilter || undefined,
      status: statusFilter || undefined,
      sort: "final_score",
    })
      .then((responseItems) => {
        if (!mounted) {
          return;
        }
        setItems(responseItems);
        setSelectedId((currentId) => {
          if (currentId && responseItems.some((item) => item.id === currentId)) {
            return currentId;
          }
          return responseItems[0]?.id ?? null;
        });
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
  }, [statusFilter, typeFilter]);

  useEffect(() => {
    if (!selectedId) {
      setEvidences([]);
      setSelectedEvidenceId(null);
      return;
    }
    let mounted = true;
    setEvidenceLoading(true);
    setFeedbackState(null);
    listEvidences(selectedId)
      .then((responseItems) => {
        if (!mounted) {
          return;
        }
        setEvidences(responseItems);
        setSelectedEvidenceId(responseItems[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load evidences");
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
  }, [selectedId]);

  const selectedItem = useMemo(() => {
    return items.find((item) => item.id === selectedId) ?? null;
  }, [items, selectedId]);

  const selectedEvidence = useMemo(() => {
    return evidences.find((item) => item.id === selectedEvidenceId) ?? null;
  }, [evidences, selectedEvidenceId]);

  async function handleStatusChange(status: IntelligenceStatus) {
    if (!selectedItem) {
      return;
    }
    const updated = await updateIntelligenceStatus(selectedItem.id, status);
    setItems((currentItems) =>
      currentItems.map((item) => (item.id === updated.id ? updated : item)),
    );
  }

  async function handleFeedback(feedbackType: FeedbackType) {
    if (!selectedItem) {
      return;
    }
    const feedback = await submitFeedback(selectedItem.id, feedbackType);
    setFeedbackState(feedback.feedbackType);
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_460px]">
      <section className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="text-base font-semibold">Intelligence 列表</h2>
            <p className="mt-1 text-sm text-[#6b7280]">规则评分、证据数量和处理状态</p>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <FilterSelect
              label="类型"
              onChange={setTypeFilter}
              options={typeOptions}
              value={typeFilter}
            />
            <FilterSelect
              label="状态"
              onChange={setStatusFilter}
              options={statusOptions}
              value={statusFilter}
            />
          </div>
        </div>

        {loading ? <p className="text-sm text-[#6b7280]">加载情报中</p> : null}
        {error ? (
          <p className="mb-4 rounded-md border border-[#fecdd3] bg-[#fff1f2] px-3 py-2 text-sm text-[#be123c]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {items.map((item) => (
            <button
              className={`rounded-md border p-4 text-left transition ${
                item.id === selectedId
                  ? "border-[#0f766e] bg-[#ecfdf5]"
                  : "border-[#dfe3ea] bg-white hover:border-[#94a3b8]"
              }`}
              key={item.id}
              onClick={() => setSelectedId(item.id)}
              type="button"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold leading-6">{item.title}</h3>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#6b7280]">
                    {item.summary}
                  </p>
                </div>
                <ScoreBadge score={item.finalScore} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Tag className={typeClass[item.intelligenceType]} label={item.intelligenceType} />
                <Tag className={statusClass[item.status]} label={item.status} />
                <Tag className="bg-[#f1f5f9] text-[#475569]" label={item.domain} />
                <Tag
                  className="bg-[#f7f8fa] text-[#374151]"
                  label={`${item.evidenceCount} evidences`}
                />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
                <MiniScore label="impact" value={item.impactScore} />
                <MiniScore label="confidence" value={item.confidenceScore} />
                <MiniScore label="novelty" value={item.noveltyScore} />
                <MiniScore label="urgency" value={item.urgencyScore} />
              </div>
            </button>
          ))}
          {!loading && items.length === 0 ? (
            <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
              暂无情报
            </div>
          ) : null}
        </div>
      </section>

      <aside className="rounded-lg border border-[#dfe3ea] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">情报详情</h2>
            <p className="mt-1 text-sm text-[#6b7280]">摘要、证据链和人工反馈</p>
          </div>
          <FileSearch size={20} className="text-[#6b7280]" aria-hidden="true" />
        </div>

        {selectedItem ? (
          <div className="grid gap-5">
            <div className="rounded-md border border-[#dfe3ea] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold leading-6">{selectedItem.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#4b5563]">{selectedItem.summary}</p>
                  <Link
                    className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-[#0f766e]"
                    href={`/intelligence/${selectedItem.id}`}
                  >
                    打开详情页
                  </Link>
                </div>
                <ScoreBadge score={selectedItem.finalScore} />
              </div>
              <div className="mt-4 grid gap-2">
                <ScoreBar label="Impact" value={selectedItem.impactScore} />
                <ScoreBar label="Confidence" value={selectedItem.confidenceScore} />
                <ScoreBar label="Novelty" value={selectedItem.noveltyScore} />
                <ScoreBar label="Urgency" value={selectedItem.urgencyScore} />
              </div>
            </div>

            <div className="rounded-md border border-[#dfe3ea] p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold">状态</h3>
                <ShieldCheck size={17} className="text-[#6b7280]" aria-hidden="true" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                {(["reviewed", "following", "dismissed", "converted"] as IntelligenceStatus[]).map(
                  (status) => (
                    <button
                      className={`rounded-md border px-3 py-2 text-xs font-semibold transition ${
                        selectedItem.status === status
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
            </div>

            <div className="rounded-md border border-[#dfe3ea] p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Evidence Timeline</h3>
                <RadioTower size={17} className="text-[#6b7280]" aria-hidden="true" />
              </div>
              {evidenceLoading ? <p className="text-sm text-[#6b7280]">加载证据中</p> : null}
              <div className="grid gap-2">
                {evidences.map((evidence) => (
                  <button
                    className={`rounded-md border px-3 py-3 text-left text-sm transition ${
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
                        <p className="font-semibold">{evidence.title}</p>
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
                {!evidenceLoading && evidences.length === 0 ? (
                  <p className="rounded-md border border-dashed border-[#dfe3ea] p-5 text-sm text-[#6b7280]">
                    暂无证据
                  </p>
                ) : null}
              </div>
            </div>

            <AuditPanel evidence={selectedEvidence} />

            <div className="rounded-md border border-[#dfe3ea] p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Feedback</h3>
                <MessageSquare size={17} className="text-[#6b7280]" aria-hidden="true" />
              </div>
              <div className="grid grid-cols-3 gap-2">
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
                  icon={ListFilter}
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
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-[#dfe3ea] p-8 text-sm text-[#6b7280]">
            选择一条情报查看证据
          </div>
        )}
      </aside>
    </div>
  );
}

function FilterSelect({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  value: string;
}) {
  return (
    <label className="grid gap-1 text-xs font-semibold text-[#6b7280]">
      {label}
      <select
        className="h-9 rounded-md border border-[#dfe3ea] bg-white px-2 text-sm font-normal text-[#111827]"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option.label} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-md bg-[#111827] text-white">
      <span className="text-base font-semibold">{score.toFixed(0)}</span>
      <span className="text-[10px] uppercase text-[#d1d5db]">score</span>
    </div>
  );
}

function Tag({ className, label }: { className?: string; label: string }) {
  return (
    <span className={`rounded-md px-2.5 py-1 text-xs font-semibold ${className ?? ""}`}>
      {label}
    </span>
  );
}

function MiniScore({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-[#f7f8fa] px-3 py-2 text-xs">
      <span className="text-[#6b7280]">{label}</span>
      <p className="mt-1 font-semibold">{value.toFixed(1)}</p>
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

function AuditPanel({ evidence }: { evidence: Evidence | null }) {
  return (
    <div className="rounded-md border border-[#dfe3ea] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">审计抽屉</h3>
        <FileSearch size={17} className="text-[#6b7280]" aria-hidden="true" />
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
              className="break-all rounded-md border border-[#dfe3ea] px-3 py-2 text-sm text-[#0f766e]"
              href={evidence.url}
              rel="noreferrer"
              target="_blank"
            >
              {evidence.url}
            </a>
          ) : null}
          {evidence.screenshotUrl ? (
            <img
              alt={evidence.title}
              className="max-h-56 w-full rounded-md border border-[#dfe3ea] object-cover"
              src={evidence.screenshotUrl}
            />
          ) : null}
          <pre className="max-h-64 overflow-auto rounded-md bg-[#111827] p-3 text-xs leading-5 text-[#e5e7eb]">
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
