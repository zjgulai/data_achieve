"use client";

import {
  CheckCircle2,
  ExternalLink,
  FileSearch,
  ListFilter,
  MessageSquare,
  RadioTower,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  listEvidences,
  listIntelligence,
  submitFeedback,
  updateIntelligenceStatus,
} from "@/lib/api/intelligence";
import { cn } from "@/lib/utils";
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
  new: "bg-[#FCEBF0] text-[#C25B6E]",
  reviewed: "bg-[#F5F0FF] text-[#6E5CF6]",
  following: "bg-[#EAF8EE] text-[#2EBA62]",
  dismissed: "bg-[#FBF8F5] text-[#86868B]",
  converted: "bg-[#FFF4DE] text-[#FF9800]",
};

const typeClass: Record<string, string> = {
  trend: "bg-[#EAF8EE] text-[#2EBA62]",
  risk: "bg-[#FFE5E2] text-[#FF3B30]",
  competitor: "bg-[#FCEBF0] text-[#C25B6E]",
  opportunity: "bg-[#FFF4DE] text-[#FF9800]",
  anomaly: "bg-[#FBF8F5] text-[#86868B]",
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

  const summary = useMemo(() => {
    const reviewedCount = items.filter((item) => item.status === "reviewed").length;
    const followingCount = items.filter((item) => item.status === "following").length;
    const evidenceCount = items.reduce((sum, item) => sum + item.evidenceCount, 0);
    const averageScore =
      items.length > 0
        ? items.reduce((sum, item) => sum + item.finalScore, 0) / items.length
        : 0;
    const latestUpdatedAt = latestTimestamp(items.map((item) => item.updatedAt));
    const latestCreatedAt = latestTimestamp(items.map((item) => item.createdAt));
    return { averageScore, evidenceCount, followingCount, latestCreatedAt, latestUpdatedAt, reviewedCount };
  }, [items]);

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
    <div className="grid min-w-0 gap-5">
      <section className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Tag className="bg-[#FCEBF0] text-[#C25B6E]" label="Evidence-backed" />
              <Tag className="bg-[#FBF8F5] text-[#86868B]" label="final_score 排序" />
              <Tag className="bg-[#EAF8EE] text-[#2EBA62]" label={`${summary.evidenceCount} evidence refs`} />
              <Tag
                className="bg-[#FFF4DE] text-[#FF9800]"
                label={
                  summary.latestUpdatedAt
                    ? `最新更新 ${formatRelativeTime(summary.latestUpdatedAt)}`
                    : "暂无更新"
                }
              />
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-[#1D1D1F]">情报判读工作台</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#86868B]">
              用评分、证据链和人工反馈闭合从信号到情报的判断过程。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:min-w-[480px] sm:grid-cols-4">
            <SummaryTile label="平均分" value={summary.averageScore.toFixed(1)} />
            <SummaryTile label="已复核" value={summary.reviewedCount} />
            <SummaryTile label="跟进中" value={summary.followingCount} />
            <SummaryTile
              label="最新情报"
              value={summary.latestCreatedAt ? formatRelativeTime(summary.latestCreatedAt) : "无"}
            />
          </div>
        </div>
      </section>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_460px]">
      <section className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
        <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="text-base font-semibold text-[#1D1D1F]">Intelligence 列表</h2>
            <p className="mt-1 text-sm text-[#86868B]">规则评分、证据数量和处理状态</p>
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

        {loading ? <p className="text-sm text-[#86868B]">加载情报中</p> : null}
        {error ? (
          <p className="mb-4 rounded-xl border border-[#FFD7DF] bg-[#FFF7F8] px-3 py-2 text-sm text-[#C25B6E]">
            {error}
          </p>
        ) : null}

        <div className="grid gap-3">
          {items.map((item) => (
            <button
              className={cn(
                "rounded-2xl border p-4 text-left transition-colors",
                item.id === selectedId
                  ? "border-[#C25B6E] bg-[#FFF7F8]"
                  : "border-[#EDE6DF] bg-[#FBF8F5] hover:border-[#C25B6E]",
              )}
              key={item.id}
              onClick={() => setSelectedId(item.id)}
              type="button"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold leading-6 text-[#1D1D1F]">{item.title}</h3>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#5F5757]">
                    {item.summary}
                  </p>
                </div>
                <ScoreBadge score={item.finalScore} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Tag className={typeClass[item.intelligenceType]} label={item.intelligenceType} />
                <Tag className={statusClass[item.status]} label={item.status} />
                <Tag className="bg-white text-[#86868B]" label={item.domain} />
                <Tag
                  className="bg-white text-[#5F5757]"
                  label={`${item.evidenceCount} evidences`}
                />
                <Tag
                  className="bg-white text-[#86868B]"
                  label={`更新 ${formatRelativeTime(item.updatedAt)}`}
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
            <div className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-8 text-sm text-[#86868B]">
              暂无情报
            </div>
          ) : null}
        </div>
      </section>

      <aside className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-[#1D1D1F]">情报详情</h2>
            <p className="mt-1 text-sm text-[#86868B]">摘要、证据链和人工反馈</p>
          </div>
          <FileSearch size={20} className="text-[#86868B]" aria-hidden="true" />
        </div>

        {selectedItem ? (
          <div className="grid gap-5">
            <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold leading-6 text-[#1D1D1F]">{selectedItem.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#5F5757]">{selectedItem.summary}</p>
                  <Link
                    className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-[#C25B6E]"
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
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                <DetailRow label="Created" value={formatDateTime(selectedItem.createdAt)} />
                <DetailRow label="Updated" value={formatDateTime(selectedItem.updatedAt)} />
              </div>
            </div>

            <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#1D1D1F]">状态</h3>
                <ShieldCheck size={17} className="text-[#86868B]" aria-hidden="true" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                {(["reviewed", "following", "dismissed", "converted"] as IntelligenceStatus[]).map(
                  (status) => (
                    <button
                      className={cn(
                        "rounded-xl border px-3 py-2 text-xs font-semibold transition-colors",
                        selectedItem.status === status
                          ? "border-[#C25B6E] bg-[#FFF7F8] text-[#C25B6E]"
                          : "border-[#EDE6DF] bg-white text-[#5F5757] hover:border-[#C25B6E]",
                      )}
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

            <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#1D1D1F]">Evidence Timeline</h3>
                <RadioTower size={17} className="text-[#86868B]" aria-hidden="true" />
              </div>
              {evidenceLoading ? <p className="text-sm text-[#86868B]">加载证据中</p> : null}
              <div className="grid gap-2">
                {evidences.map((evidence) => (
                  <button
                    className={cn(
                      "rounded-xl border px-3 py-3 text-left text-sm transition-colors",
                      evidence.id === selectedEvidenceId
                        ? "border-[#C25B6E] bg-[#FFF7F8]"
                        : "border-[#EDE6DF] bg-white hover:border-[#C25B6E]",
                    )}
                    key={evidence.id}
                    onClick={() => setSelectedEvidenceId(evidence.id)}
                    type="button"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-[#1D1D1F]">{evidence.title}</p>
                        <p className="mt-1 text-xs text-[#86868B]">{evidence.evidenceType}</p>
                      </div>
                      <span className="text-xs text-[#86868B]">
                        {formatDateTime(evidence.createdAt)}
                      </span>
                    </div>
                    {evidence.rawRecord ? (
                      <p className="mt-1 text-xs text-[#9E6A76]">
                        原始采集 {formatRelativeTime(evidence.rawRecord.collectedAt)}
                      </p>
                    ) : null}
                    {evidence.excerpt ? (
                      <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#5F5757]">
                        {evidence.excerpt}
                      </p>
                    ) : null}
                  </button>
                ))}
                {!evidenceLoading && evidences.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-[#EDE6DF] bg-white p-5 text-sm text-[#86868B]">
                    暂无证据
                  </p>
                ) : null}
              </div>
            </div>

            <AuditPanel evidence={selectedEvidence} />

            <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#1D1D1F]">Feedback</h3>
                <MessageSquare size={17} className="text-[#86868B]" aria-hidden="true" />
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
                <p className="mt-3 rounded-xl bg-white px-3 py-2 text-xs text-[#86868B]">
                  已提交：{feedbackState}
                </p>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-8 text-sm text-[#86868B]">
            选择一条情报查看证据
          </div>
        )}
      </aside>
      </div>
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
    <label className="grid gap-1 text-xs font-semibold text-[#86868B]">
      {label}
      <select
        className="h-9 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-2 text-sm font-normal text-[#1D1D1F] outline-none"
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

function SummaryTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] px-4 py-3">
      <p className="text-xs font-medium text-[#86868B]">{label}</p>
      <p className="mt-1 text-lg font-semibold text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-2xl bg-[#FCEBF0] text-[#C25B6E]">
      <span className="text-base font-semibold">{score.toFixed(0)}</span>
      <span className="text-[10px] uppercase">score</span>
    </div>
  );
}

function Tag({ className, label }: { className?: string; label: string }) {
  return (
    <span className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${className ?? ""}`}>
      {label}
    </span>
  );
}

function MiniScore({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-white px-3 py-2 text-xs">
      <span className="text-[#86868B]">{label}</span>
      <p className="mt-1 font-semibold text-[#1D1D1F]">{value.toFixed(1)}</p>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-semibold text-[#5F5757]">{label}</span>
        <span className="text-[#86868B]">{value.toFixed(1)}</span>
      </div>
      <div className="h-2 rounded-full bg-[#F5EDE8]">
        <div
          className="h-2 rounded-full bg-[#C25B6E]"
          style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
        />
      </div>
    </div>
  );
}

function AuditPanel({ evidence }: { evidence: Evidence | null }) {
  return (
    <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[#1D1D1F]">审计抽屉</h3>
        <FileSearch size={17} className="text-[#86868B]" aria-hidden="true" />
      </div>
      {evidence ? (
        <div className="grid gap-3">
          <DetailRow label="Evidence ID" value={evidence.id} />
          {evidence.signal ? (
            <TraceSection title="Signal">
              <DetailRow label="Type" value={evidence.signal.signalType} />
              <DetailRow label="Severity" value={evidence.signal.severity} />
              <DetailRow label="Delta" value={formatTraceValue(evidence.signal.delta)} />
              <DetailRow label="Confidence" value={formatTraceValue(evidence.signal.confidence)} />
            </TraceSection>
          ) : evidence.signalId ? (
            <DetailRow label="Signal ID" value={evidence.signalId} />
          ) : null}
          {evidence.entity ? (
            <TraceSection title="Entity">
              <DetailRow label="Name" value={evidence.entity.name} />
              <DetailRow label="Type" value={evidence.entity.entityType} />
              <DetailRow label="External ID" value={evidence.entity.externalId} />
            </TraceSection>
          ) : null}
          {evidence.source ? (
            <TraceSection title="Source">
              <DetailRow label="Name" value={evidence.source.name} />
              <DetailRow label="Collector" value={evidence.source.type} />
            </TraceSection>
          ) : null}
          {evidence.taskRun ? (
            <TraceSection title="Task Run">
              <DetailRow label="Run ID" value={evidence.taskRun.id} />
              <DetailRow label="Status" value={evidence.taskRun.status} />
              <DetailRow label="Records" value={String(evidence.taskRun.recordsCount)} />
              <Link
                className="inline-flex w-fit items-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 py-2 text-xs font-semibold text-[#C25B6E]"
                href={`/tasks?run=${evidence.taskRun.id}`}
              >
                打开采集任务
              </Link>
            </TraceSection>
          ) : null}
          {evidence.rawRecord ? (
            <TraceSection title="Raw Record">
              <DetailRow label="RawRecord ID" value={evidence.rawRecord.id} />
              <DetailRow label="Content Hash" value={evidence.rawRecord.contentHash} />
              <DetailRow label="Collected" value={formatDateTime(evidence.rawRecord.collectedAt)} />
              <Link
                className="inline-flex w-fit items-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 py-2 text-xs font-semibold text-[#C25B6E]"
                href={`/raw-records?record=${evidence.rawRecord.id}`}
              >
                查看原始数据
              </Link>
            </TraceSection>
          ) : evidence.rawRecordId ? (
            <DetailRow label="RawRecord ID" value={evidence.rawRecordId} />
          ) : null}
          {evidenceExternalUrl(evidence) ? (
            <a
              className="inline-flex items-center gap-2 break-all rounded-xl border border-[#EDE6DF] bg-white px-3 py-2 text-sm text-[#C25B6E]"
              href={evidenceExternalUrl(evidence) ?? undefined}
              rel="noreferrer"
              target="_blank"
            >
              <ExternalLink size={15} aria-hidden="true" />
              {evidenceExternalUrl(evidence)}
            </a>
          ) : null}
          {evidence.screenshotUrl ? (
            <Image
              alt={evidence.title}
              className="max-h-56 w-full rounded-xl border border-[#EDE6DF] object-cover"
              height={520}
              priority
              src={evidence.screenshotUrl}
              unoptimized
              width={900}
            />
          ) : null}
          {evidence.referenceMetadata ? (
            <TraceSection title="Reference Metadata">
              <pre className="max-h-64 overflow-auto rounded-xl bg-[#231A1A] p-3 text-xs leading-5 text-[#FBF8F5]">
                {formatJsonPreview(evidence.referenceMetadata)}
              </pre>
            </TraceSection>
          ) : null}
          <pre className="max-h-64 overflow-auto rounded-xl bg-[#231A1A] p-3 text-xs leading-5 text-[#FBF8F5]">
            {evidence.highlightedText ?? evidence.excerpt ?? "No highlighted text"}
          </pre>
          {evidence.rawRecord ? (
            <pre className="max-h-64 overflow-auto rounded-xl bg-[#231A1A] p-3 text-xs leading-5 text-[#FBF8F5]">
              {formatJsonPreview(evidence.rawRecord.contentPreview)}
            </pre>
          ) : null}
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-[#EDE6DF] bg-white p-5 text-sm text-[#86868B]">
          暂无选中证据
        </p>
      )}
    </div>
  );
}

function TraceSection({ children, title }: { children: ReactNode; title: string }) {
  return (
    <div className="grid gap-2 rounded-xl border border-[#EDE6DF] bg-white p-3">
      <p className="text-xs font-semibold uppercase text-[#86868B]">{title}</p>
      <div className="grid gap-2">{children}</div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white px-3 py-2 text-sm">
      <span className="text-[#86868B]">{label}</span>
      <p className="mt-1 break-all font-medium text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function evidenceExternalUrl(evidence: Evidence) {
  return (
    evidence.url ??
    evidence.rawRecord?.sourceUrl ??
    evidence.entity?.canonicalUrl ??
    evidence.source?.url ??
    null
  );
}

function formatTraceValue(value: unknown) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return typeof value === "number" ? value.toFixed(2) : String(value);
}

function formatDateTime(value: string) {
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

function formatRelativeTime(value: string) {
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

function latestTimestamp(values: string[]) {
  const timestamps = values
    .map((value) => new Date(value).getTime())
    .filter((value) => Number.isFinite(value));
  if (timestamps.length === 0) {
    return null;
  }
  return new Date(Math.max(...timestamps)).toISOString();
}

function formatJsonPreview(value: Record<string, unknown> | unknown[] | string) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
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
      className="flex items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 py-2 text-xs font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]"
      onClick={onClick}
      type="button"
    >
      <Icon size={15} aria-hidden="true" />
      {label}
    </button>
  );
}
