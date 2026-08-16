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
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { useProjectSelection } from "@/components/layout/project-selection-provider";
import {
  getIntelligence,
  listEvidences,
  submitFeedback,
  updateIntelligenceStatus,
} from "@/lib/api/intelligence";
import { getSignalSnapshotCompare } from "@/lib/api/signals";
import { buildAuditFacts, type AuditFact } from "@/lib/audit-display";
import {
  buildIntelligenceDetailHref,
  buildIntelligenceListHref,
  buildProjectScopedHref,
  readIntelligenceNavigationContext,
  type IntelligenceNavigationContext,
} from "@/lib/intelligence-navigation";
import { cn } from "@/lib/utils";
import { WorkbenchDistributionRow, WorkbenchTraceDetailRow } from "@/components/common/workbench-ui";
import type {
  Evidence,
  FeedbackType,
  IntelligenceItem,
  IntelligenceStatus,
} from "@/types/intelligence";
import type { SignalSnapshotCompare } from "@/types/signal";

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

const initialNavigationContext: IntelligenceNavigationContext = {
  evidenceId: null,
  intelligenceId: null,
  projectId: null,
  scope: "all",
  status: "",
  type: "",
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
  const [navigationContext, setNavigationContext] =
    useState<IntelligenceNavigationContext>(initialNavigationContext);
  const [navigationReady, setNavigationReady] = useState(false);
  const {
    clearProjectFilterApplied,
    loading: projectSelectionLoading,
    markProjectFilterApplied,
    selectedProject,
    selectedProjectId,
  } = useProjectSelection();

  useEffect(() => {
    function restoreNavigationContext() {
      const context = readIntelligenceNavigationContext(window.location.search);
      setNavigationContext(context);
      setSelectedEvidenceId(context.evidenceId);
      setNavigationReady(true);
    }

    restoreNavigationContext();
    window.addEventListener("popstate", restoreNavigationContext);
    return () => window.removeEventListener("popstate", restoreNavigationContext);
  }, []);

  useEffect(() => {
    if (!navigationReady || projectSelectionLoading) {
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);
    setItem(null);
    setEvidences([]);
    clearProjectFilterApplied();
    Promise.all([getIntelligence(intelligenceId), listEvidences(intelligenceId)])
      .then(([intelligence, evidenceItems]) => {
        if (!mounted) {
          return;
        }
        if (selectedProjectId && intelligence.projectId !== selectedProjectId) {
          setSelectedEvidenceId(null);
          setError(
            "当前情报不属于所选 Project；已停止显示 Evidence。请返回情报列表查看当前范围。",
          );
          return;
        }
        setItem(intelligence);
        setEvidences(evidenceItems);
        setSelectedEvidenceId((currentId) => {
          if (currentId && evidenceItems.some((evidence) => evidence.id === currentId)) {
            return currentId;
          }
          return evidenceItems[0]?.id ?? null;
        });
        if (selectedProjectId) {
          markProjectFilterApplied(selectedProjectId);
        }
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
  }, [
    clearProjectFilterApplied,
    intelligenceId,
    markProjectFilterApplied,
    navigationContext.evidenceId,
    navigationReady,
    projectSelectionLoading,
    selectedProjectId,
  ]);

  const selectedEvidence = useMemo(() => {
    return evidences.find((evidence) => evidence.id === selectedEvidenceId) ?? null;
  }, [evidences, selectedEvidenceId]);

  const detailNavigationContext = useMemo(
    () => ({
      ...navigationContext,
      evidenceId: selectedEvidenceId,
      intelligenceId,
      projectId: selectedProjectId,
    }),
    [intelligenceId, navigationContext, selectedEvidenceId, selectedProjectId],
  );
  const listHref = buildIntelligenceListHref(detailNavigationContext);

  useEffect(() => {
    if (!navigationReady || projectSelectionLoading) {
      return;
    }
    const nextHref = buildIntelligenceDetailHref(intelligenceId, detailNavigationContext);
    const currentHref = `${window.location.pathname}${window.location.search}`;
    if (nextHref !== currentHref) {
      window.history.replaceState(window.history.state, "", nextHref);
    }
  }, [detailNavigationContext, intelligenceId, navigationReady, projectSelectionLoading]);

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
    return <p className="text-sm text-[#86868B]">加载情报中</p>;
  }

  if (error || !item) {
    return (
      <div
        className="grid gap-3 rounded-[var(--radius-3)] border border-[var(--state-danger)] bg-[var(--surface-primary)] p-4 text-sm text-[var(--state-danger)]"
        role="alert"
      >
        <p>{error ?? "Intelligence item not found"}</p>
        <Link
          className="inline-flex min-h-[var(--touch-target)] w-fit items-center gap-2 rounded-[var(--radius-2)] border border-[var(--border-strong)] px-3 font-semibold text-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
          href={listHref}
        >
          <ArrowLeft size={16} aria-hidden="true" />
          返回当前 Project 的情报列表
        </Link>
      </div>
    );
  }

  return (
    <div className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_430px]">
      <section
        className="flex min-w-0 flex-col gap-2 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between 2xl:col-span-2"
        data-testid="intelligence-detail-context-strip"
      >
        <div className="min-w-0">
          <p className="text-xs font-medium text-[var(--text-tertiary)]">浏览上下文</p>
          <p className="truncate text-sm font-semibold text-[var(--text-primary)]">
            当前 Project · {selectedProject?.name ?? "全部项目"}
          </p>
        </div>
        <p className="text-xs leading-5 text-[var(--text-secondary)]">
          类型 {navigationContext.type || "全部"} · 状态 {navigationContext.status || "全部"} ·
          Scope {navigationContext.scope}
        </p>
      </section>
      <section className="grid gap-5">
        <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <Link
            className="mb-4 inline-flex min-h-[var(--touch-target)] items-center gap-2 rounded-[var(--radius-2)] text-sm font-semibold text-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
            href={listHref}
          >
            <ArrowLeft size={16} aria-hidden="true" />
            情报列表
          </Link>
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0">
              <h2 className="text-xl font-semibold leading-8 text-[#1D1D1F]">{item.title}</h2>
              <div className="mt-3 flex flex-wrap gap-2">
                <Tag className={typeClass[item.intelligenceType]} label={item.intelligenceType} />
                <Tag className={statusClass[item.status]} label={item.status} />
                <Tag className="bg-[#FBF8F5] text-[#86868B]" label={item.domain} />
                <Tag
                  className="bg-[#FBF8F5] text-[#5F5757]"
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

        <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#1D1D1F]">AI Summary</h2>
            <FileSearch size={18} className="text-[#86868B]" aria-hidden="true" />
          </div>
          <div className="grid gap-2">
            {summaryClaims(item.summary).map((claim, index) => {
              const evidence = evidences[index % Math.max(evidences.length, 1)] ?? null;
              const selected = evidence?.id === selectedEvidenceId;
              return (
                <button
                  className={cn(
                    "rounded-xl border px-3 py-3 text-left text-sm leading-6 transition-colors",
                    selected
                      ? "border-[#C25B6E] bg-[#FFF7F8] text-[#7A3D49]"
                      : "border-[#EDE6DF] bg-[#FBF8F5] text-[#5F5757] hover:border-[#C25B6E]",
                  )}
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

        <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#1D1D1F]">Snapshot Compare</h2>
            <SplitSquareHorizontal size={18} className="text-[#86868B]" aria-hidden="true" />
          </div>
          {compareLoading ? <p className="text-sm text-[#86868B]">加载对比中</p> : null}
          {snapshotCompare ? (
            <SnapshotComparePanel compare={snapshotCompare} />
          ) : (
            <div className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-5 text-sm text-[#86868B]">
              当前证据暂无快照对比
            </div>
          )}
        </div>
      </section>

      <aside className="grid gap-5">
        <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#1D1D1F]">Evidence Timeline</h2>
            <RadioTower size={18} className="text-[#86868B]" aria-hidden="true" />
          </div>
          <div className="grid gap-2">
            {evidences.map((evidence) => (
              <button
                aria-pressed={evidence.id === selectedEvidenceId}
                className={cn(
                  "rounded-xl border px-3 py-3 text-left transition-colors",
                  evidence.id === selectedEvidenceId
                    ? "border-[#C25B6E] bg-[#FFF7F8]"
                    : "border-[#EDE6DF] bg-[#FBF8F5] hover:border-[#C25B6E]",
                )}
                data-testid={`intelligence-detail-evidence-${evidence.id}`}
                key={evidence.id}
                onClick={() => setSelectedEvidenceId(evidence.id)}
                type="button"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[#1D1D1F]">{evidence.title}</p>
                    <p className="mt-1 text-xs text-[#86868B]">{evidence.evidenceType}</p>
                  </div>
                  <span className="text-xs text-[#86868B]">
                    {new Date(evidence.createdAt).toLocaleString()}
                  </span>
                </div>
                {evidence.excerpt ? (
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#5F5757]">
                    {evidence.excerpt}
                  </p>
                ) : null}
              </button>
            ))}
          </div>
        </div>

        <AuditDrawer evidence={selectedEvidence} projectId={selectedProjectId} />

        <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#1D1D1F]">状态与反馈</h2>
            <ShieldCheck size={18} className="text-[#86868B]" aria-hidden="true" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            {(["reviewed", "following", "dismissed", "converted"] as IntelligenceStatus[]).map(
              (status) => (
                <button
                  className={cn(
                    "rounded-xl border px-3 py-2 text-xs font-semibold transition-colors",
                    item.status === status
                      ? "border-[#C25B6E] bg-[#FFF7F8] text-[#C25B6E]"
                      : "border-[#EDE6DF] bg-[#FBF8F5] text-[#5F5757] hover:border-[#C25B6E]",
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
            <p className="mt-3 rounded-xl bg-[#FBF8F5] px-3 py-2 text-xs text-[#86868B]">
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
        <SnapshotBox label="前次快照" value={compare.previousSnapshot} />
        <SnapshotBox label="当前快照" value={compare.currentSnapshot} />
      </div>
      <div className="overflow-hidden rounded-2xl border border-[#EDE6DF]">
        <div className="grid grid-cols-[1fr_1fr_1fr_1fr] bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#86868B]">
          <span>Metric</span>
          <span>Old</span>
          <span>New</span>
          <span>Delta</span>
        </div>
        {compare.metricsDiff.map((item) => (
          <div
            className="grid grid-cols-[1fr_1fr_1fr_1fr] border-t border-[#EDE6DF] px-3 py-2 text-xs"
            key={item.metric}
          >
            <span className="font-semibold text-[#1D1D1F]">{item.metric}</span>
            <span className="break-all text-[#86868B]">{formatValue(item.previousValue)}</span>
            <span className="break-all text-[#1D1D1F]">{formatValue(item.currentValue)}</span>
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
  const metricFacts = buildAuditFacts(value.metrics, 8);
  return (
    <div className="rounded-2xl border border-[#EDE6DF] bg-[#FBF8F5] p-4">
      <p className="text-xs font-semibold uppercase text-[#86868B]">{label}</p>
      <p className="mt-2 break-all text-sm font-semibold text-[#1D1D1F]">
        快照批次 {formatShortTraceId(value.id)}
      </p>
      <p className="mt-1 text-xs text-[#86868B]">{new Date(value.capturedAt).toLocaleString()}</p>
      {metricFacts.length > 0 ? (
        <div className="mt-3">
          <AuditFactSection facts={metricFacts} title="指标摘要" />
        </div>
      ) : null}
    </div>
  );
}

function AuditDrawer({
  evidence,
  projectId,
}: {
  evidence: Evidence | null;
  projectId: string | null;
}) {
  const referenceFacts = evidence?.referenceMetadata
    ? buildAuditFacts(evidence.referenceMetadata, 6)
    : [];
  const rawContentFacts = evidence?.rawRecord
    ? buildAuditFacts(evidence.rawRecord.contentPreview, 10)
    : [];

  return (
    <div className="rounded-2xl border border-[#E9E5E2] bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-[#1D1D1F]">审计抽屉</h2>
        <FileSearch size={18} className="text-[#86868B]" aria-hidden="true" />
      </div>
      {evidence ? (
        <div className="grid gap-3">
          <WorkbenchTraceDetailRow surface="warm" label="证据类型" value={evidence.evidenceType} />
          {evidence.entity ? (
            <TraceSection title="Entity">
              <WorkbenchTraceDetailRow surface="warm" label="Name" value={evidence.entity.name} />
              <WorkbenchTraceDetailRow surface="warm" label="Type" value={evidence.entity.entityType} />
              <WorkbenchTraceDetailRow surface="warm" label="External ID" value={evidence.entity.externalId} />
              <WorkbenchTraceDetailRow surface="warm" label="Domain" value={evidence.entity.domain} />
            </TraceSection>
          ) : null}
          {evidence.signal ? (
            <TraceSection title="Signal">
              <WorkbenchTraceDetailRow surface="warm" label="Type" value={evidence.signal.signalType} />
              <WorkbenchTraceDetailRow surface="warm" label="Severity" value={evidence.signal.severity} />
              <WorkbenchTraceDetailRow surface="warm" label="Previous" value={formatValue(evidence.signal.previousValue)} />
              <WorkbenchTraceDetailRow surface="warm" label="Current" value={formatValue(evidence.signal.currentValue)} />
              <WorkbenchTraceDetailRow surface="warm" label="Delta" value={formatValue(evidence.signal.delta)} />
              <WorkbenchTraceDetailRow surface="warm" label="Confidence" value={formatValue(evidence.signal.confidence)} />
            </TraceSection>
          ) : null}
          {evidence.source ? (
            <TraceSection title="Source">
              <WorkbenchTraceDetailRow surface="warm" label="Name" value={evidence.source.name} />
              <WorkbenchTraceDetailRow surface="warm" label="Collector" value={evidence.source.type} />
              <WorkbenchTraceDetailRow surface="warm" label="Enabled" value={evidence.source.enabled ? "是" : "否"} />
            </TraceSection>
          ) : null}
          {evidence.taskRun ? (
            <TraceSection title="采集运行">
              <WorkbenchTraceDetailRow surface="warm" label="Status" value={evidence.taskRun.status} />
              <WorkbenchTraceDetailRow surface="warm" label="Records" value={String(evidence.taskRun.recordsCount)} />
              <WorkbenchTraceDetailRow surface="warm" label="Entities" value={String(evidence.taskRun.entitiesCount)} />
              {evidence.taskRun.startedAt ? (
                <WorkbenchTraceDetailRow surface="warm" label="Started" value={formatDateTime(evidence.taskRun.startedAt)} />
              ) : null}
              <Link
                className="inline-flex w-fit items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-sm font-semibold text-[#C25B6E]"
                href={buildProjectScopedHref(`/tasks?run=${evidence.taskRun.id}`, projectId)}
              >
                打开采集任务
              </Link>
            </TraceSection>
          ) : null}
          {evidence.rawRecord ? (
            <TraceSection title="原始事实">
              <WorkbenchTraceDetailRow surface="warm" label="Record Type" value={evidence.rawRecord.recordType} />
              <WorkbenchTraceDetailRow surface="warm" label="Collected" value={formatDateTime(evidence.rawRecord.collectedAt)} />
              <Link
                className="inline-flex w-fit items-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-sm font-semibold text-[#C25B6E]"
                href={buildProjectScopedHref(
                  `/raw-records?record=${evidence.rawRecord.id}`,
                  projectId,
                )}
              >
                查看原始数据
              </Link>
            </TraceSection>
          ) : null}
          {evidenceExternalUrl(evidence) ? (
            <a
              className="inline-flex items-center gap-2 break-all rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-sm text-[#C25B6E]"
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
              className="max-h-64 w-full rounded-xl border border-[#EDE6DF] object-cover"
              height={520}
              priority
              src={evidence.screenshotUrl}
              unoptimized
              width={900}
            />
          ) : null}
          {referenceFacts.length > 0 ? (
            <AuditFactSection facts={referenceFacts} title="证据定位" />
          ) : null}
          <TraceSection title="证据摘录">
            <p className="rounded-xl bg-[#FBF8F5] px-3 py-2 text-sm leading-6 text-[#1D1D1F]">
              {evidence.highlightedText ?? evidence.excerpt ?? "暂无证据摘录"}
            </p>
          </TraceSection>
          {rawContentFacts.length > 0 ? (
            <AuditFactSection facts={rawContentFacts} title="原始内容摘要" />
          ) : null}
        </div>
      ) : (
        <p className="rounded-2xl border border-dashed border-[#EDE6DF] bg-[#FBF8F5] p-5 text-sm text-[#86868B]">
          暂无选中证据
        </p>
      )}
    </div>
  );
}

function AuditFactSection({ facts, title }: { facts: AuditFact[]; title: string }) {
  return (
    <TraceSection title={title}>
      <div className="grid gap-2">
        {facts.map((fact) => (
          <WorkbenchTraceDetailRow surface="warm" key={`${title}-${fact.label}-${fact.value}`} label={fact.label} value={fact.value} />
        ))}
      </div>
    </TraceSection>
  );
}

function TraceSection({ children, title }: { children: ReactNode; title: string }) {
  return (
    <div className="grid gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
      <p className="text-xs font-semibold uppercase text-[#86868B]">{title}</p>
      <div className="grid gap-2">{children}</div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <div className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-2xl bg-[#FCEBF0] text-[#C25B6E]">
      <span className="text-lg font-semibold">{score.toFixed(0)}</span>
      <span className="text-[10px] uppercase">score</span>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <WorkbenchDistributionRow
      label={label}
      size="compact"
      tone="rose"
      value={value.toFixed(1)}
      width={value}
    />
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

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("zh-CN");
}

function formatShortTraceId(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
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
      className="flex items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 text-xs font-semibold text-[#5F5757] transition-colors hover:border-[#C25B6E] hover:text-[#C25B6E]"
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
    <span className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${className ?? ""}`}>
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
