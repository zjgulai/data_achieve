"use client";

import {
  AlertTriangle,
  ArrowLeft,
  ChevronRight,
  FileSearch,
  Layers3,
  Loader2,
  Network,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  WorkbenchFact,
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import { previewCapabilityDiscovery } from "@/lib/api/capability-discovery";
import type {
  CapabilityDiscoveryCandidateAssertion,
  CapabilityDiscoveryEvidence,
  CapabilityDiscoveryPlatform,
  CapabilityDiscoveryPreview,
} from "@/types/capability-discovery";

type CapabilityDiscoveryWorkspaceProps = {
  loadPreview?: () => Promise<CapabilityDiscoveryPreview>;
};

const platformLabels: Record<CapabilityDiscoveryPlatform, string> = {
  instagram: "Instagram",
  linkedin: "LinkedIn",
  reddit: "Reddit",
  threads: "Threads",
  tiktok: "TikTok",
  x: "X",
  youtube: "YouTube",
};

const resourceLabels = {
  commerce_ads: "商业与广告",
  content: "内容",
  conversation: "评论与对话",
  creator: "创作者",
  media_live: "直播媒体",
  metrics: "指标",
  relationship_graph: "关系图谱",
  topic: "主题",
} as const;

const operationLabels = {
  backfill_history: "历史回填",
  batch_parse: "批量解析",
  export_download: "导出下载",
  list_enumerate: "列表枚举",
  monitor_incremental: "增量监测",
  resolve_detail: "详情解析",
  search_discover: "搜索发现",
} as const;

export function CapabilityDiscoveryWorkspace({
  loadPreview = previewCapabilityDiscovery,
}: CapabilityDiscoveryWorkspaceProps) {
  const [preview, setPreview] = useState<CapabilityDiscoveryPreview | null>(
    null,
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(
    null,
  );
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(
    null,
  );
  const returnFocusToRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let cancelled = false;
    setPreview(null);
    setLoadError(null);

    void loadPreview()
      .then((nextPreview) => {
        if (!cancelled) {
          setPreview(nextPreview);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setLoadError(
            cause instanceof Error
              ? cause.message
              : "capability_discovery_preview_unavailable",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [loadPreview]);

  const evidenceBySourceId = useMemo(() => {
    if (!preview) {
      return new Map<string, CapabilityDiscoveryEvidence>();
    }
    return new Map(
      preview.sourceSnapshots.flatMap((source) => {
        const evidence = preview.evidence.find(
          (item) => item.sourceUrl === source.sourceUrl,
        );
        return evidence ? [[source.fixtureId, evidence] as const] : [];
      }),
    );
  }, [preview]);

  const visibleCandidates = useMemo(() => {
    if (!preview) {
      return [];
    }
    if (!selectedSourceId) {
      return preview.candidateAssertions;
    }
    const evidenceId = evidenceBySourceId.get(selectedSourceId)?.evidenceId;
    return evidenceId
      ? preview.candidateAssertions.filter((candidate) =>
          candidate.evidenceRefs.includes(evidenceId),
        )
      : [];
  }, [evidenceBySourceId, preview, selectedSourceId]);

  const selectedCandidate = useMemo(
    () =>
      preview?.candidateAssertions.find(
        (candidate) => candidate.candidateId === selectedCandidateId,
      ) ?? null,
    [preview, selectedCandidateId],
  );
  const selectedEvidence = useMemo(
    () =>
      preview?.evidence.find(
        (evidence) => evidence.evidenceId === selectedEvidenceId,
      ) ?? null,
    [preview, selectedEvidenceId],
  );
  const warnings = useMemo(
    () =>
      preview?.diagnostics.filter(
        (diagnostic) => diagnostic.severity === "warning",
      ) ?? [],
    [preview],
  );

  function openCandidate(
    candidate: CapabilityDiscoveryCandidateAssertion,
    trigger: HTMLElement,
  ) {
    returnFocusToRef.current = trigger;
    setSelectedEvidenceId(null);
    setSelectedCandidateId(candidate.candidateId);
  }

  function closeCandidate() {
    setSelectedCandidateId(null);
    setSelectedEvidenceId(null);
    requestAnimationFrame(() => returnFocusToRef.current?.focus());
  }

  useEffect(() => {
    if (!selectedCandidate) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeCandidate();
      } else if (event.key === "Tab") {
        keepFocusInsideDialog(event, dialogRef.current);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [selectedCandidate]);

  if (loadError) {
    return (
      <WorkbenchPanel
        icon={AlertTriangle}
        label="Discovery Preview error"
        title="能力发现 Preview 加载失败"
      >
        <p
          className="rounded-xl border border-[#FFD0C8] bg-[#FFF1EC] p-4 text-sm font-semibold text-[#B85F4F]"
          role="alert"
        >
          {loadError} · 未使用 mock 回退
        </p>
      </WorkbenchPanel>
    );
  }

  if (!preview) {
    return (
      <p
        className="inline-flex min-h-28 items-center justify-center gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-5 text-sm font-semibold text-[#7A625A]"
        role="status"
      >
        <Loader2 className="animate-spin" size={18} aria-hidden="true" />
        正在回放 4 份离线来源快照…
      </p>
    );
  }

  return (
    <div className="grid min-w-0 gap-5">
      <section
        aria-label="离线快照边界"
        className="grid gap-4 rounded-2xl border border-[#E6B9AB] bg-[#FFF1EC] p-4 shadow-[0_16px_42px_rgba(72,45,38,0.06)] sm:p-5"
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase text-[#B85F4F]">
              <ShieldCheck size={15} aria-hidden="true" />
              离线快照边界
            </p>
            <h2 className="mt-1 text-xl font-semibold text-[#2E201C]">
              发现结果是待核验 Candidate，不进入正式能力目录
            </h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[#7A625A]">
              本页只重放仓库内的公开市场与官方文档 Fixture；不读取凭证、不访问 Provider、不写数据库。
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <WorkbenchTag tone="amber">待核验</WorkbenchTag>
            <WorkbenchTag tone="rose">不可执行</WorkbenchTag>
            <WorkbenchTag tone="rose">不可发布</WorkbenchTag>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <WorkbenchFact label="provider_call" value="false" />
          <WorkbenchFact label="browser_run" value="false" />
          <WorkbenchFact label="database_write" value="false" />
          <WorkbenchFact label="workflow_run_created" value="false" />
        </div>
        <p className="text-xs font-semibold text-[#7A625A]">
          provider_call=false · browser_run=false · database_write=false · workflow_run_created=false
        </p>
      </section>

      <WorkbenchPanel
        action={<WorkbenchTag tone="neutral">{preview.evidenceGrade}</WorkbenchTag>}
        icon={Layers3}
        label="Fixture discovery summary"
        subtitle="数字来自同一份确定性 Preview 响应。"
        title="发现摘要"
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <WorkbenchFact
            label="来源"
            value={`${preview.summary.sourceCount} 份（市场 ${preview.summary.marketSourceCount} / 官方 ${preview.summary.officialDocSourceCount}）`}
          />
          <WorkbenchFact
            label="Candidate"
            value={`${preview.summary.candidateAssertionCount} 个待核验`}
          />
          <WorkbenchFact
            label="Evidence"
            value={`${preview.summary.evidenceCount} 个 Evidence`}
          />
          <WorkbenchFact
            label="Warnings"
            value={`${preview.summary.warningCount} 个公开声明缺口`}
          />
        </div>
      </WorkbenchPanel>

      <WorkbenchPanel
        icon={Network}
        label="Source pipeline"
        subtitle="选择来源只会筛选本页 Candidate，不会重新抓取网页。"
        title="Source → Parser → Candidate → Evidence → 待核验"
      >
        <div className="grid gap-3 lg:grid-cols-2">
          {preview.sourceSnapshots.map((source) => {
            const evidence = evidenceBySourceId.get(source.fixtureId);
            const candidateCount = evidence
              ? preview.candidateAssertions.filter((candidate) =>
                  candidate.evidenceRefs.includes(evidence.evidenceId),
                ).length
              : 0;
            const selected = selectedSourceId === source.fixtureId;
            return (
              <article
                className={`grid min-w-0 gap-3 rounded-2xl border p-4 ${
                  selected
                    ? "border-[#C96F5C] bg-[#FFF1EC]"
                    : "border-[#E8D4CB] bg-[#FFFDFC]"
                }`}
                data-discovery-source-id={source.fixtureId}
                key={source.fixtureId}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase text-[#B47767]">
                      {source.sourceKind === "public_market"
                        ? "公开市场来源"
                        : "官方文档来源"}
                    </p>
                    <h3 className="mt-1 text-base font-semibold text-[#2E201C]">
                      {source.sourceName}
                    </h3>
                  </div>
                  <WorkbenchTag tone="neutral">{candidateCount} Candidate</WorkbenchTag>
                </div>
                <div className="grid gap-2 text-xs text-[#7A625A] sm:grid-cols-2">
                  <SourceFact label="Parser" value={source.parserId} />
                  <SourceFact label="Observed" value={source.observedAt} />
                </div>
                <button
                  aria-pressed={selected}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[#D9C4BA] bg-white px-3 text-sm font-semibold text-[#7D4F43] outline-none transition hover:border-[#C96F5C] hover:bg-[#FFF8F5] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                  onClick={() =>
                    setSelectedSourceId(selected ? null : source.fixtureId)
                  }
                  type="button"
                >
                  查看 {source.sourceName} 的 Candidate
                  <ChevronRight size={16} aria-hidden="true" />
                </button>
              </article>
            );
          })}
        </div>
      </WorkbenchPanel>

      <WorkbenchPanel
        action={
          selectedSourceId ? (
            <button
              className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7D4F43] outline-none transition hover:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
              onClick={() => setSelectedSourceId(null)}
              type="button"
            >
              <ArrowLeft size={15} aria-hidden="true" />
              查看全部
            </button>
          ) : null
        }
        icon={FileSearch}
        label="Candidate review queue"
        subtitle="仅展示来源声明及约束，不提供核验、执行或发布操作。"
        title={`Candidate 列表 · ${visibleCandidates.length}`}
      >
        <div className="grid gap-3 lg:grid-cols-2">
          {visibleCandidates.map((candidate) => (
            <CandidateCard
              candidate={candidate}
              key={candidate.candidateId}
              onOpen={openCandidate}
            />
          ))}
        </div>
      </WorkbenchPanel>

      <WorkbenchPanel
        action={<WorkbenchTag tone="amber">{warnings.length} warnings</WorkbenchTag>}
        icon={AlertTriangle}
        label="Warning diagnostics"
        subtitle="警告不会自动生成新能力，也不会把 Candidate 提升为 Verified。"
        title="需要人工复核的来源声明"
      >
        <div className="grid gap-3 lg:grid-cols-2">
          {warnings.map((warning) => (
            <article
              className="rounded-xl border border-[#F1D6A8] bg-[#FFF9ED] p-4"
              data-discovery-warning={warning.code}
              key={`${warning.fixtureId}:${warning.sourceClaimRef}`}
            >
              <p className="text-sm font-semibold text-[#7D4F43]">
                {warning.message}
              </p>
              <p className="mt-2 break-all text-xs text-[#8B725F]">
                {warning.fixtureId} · {warning.sourceClaimRef}
              </p>
            </article>
          ))}
        </div>
      </WorkbenchPanel>

      <details className="rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 text-sm text-[#7A625A]">
        <summary className="cursor-pointer font-semibold text-[#7D4F43] outline-none focus-visible:ring-4 focus-visible:ring-[#F3D7CE]">
          高级契约与确定性标识
        </summary>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <WorkbenchFact label="schema" value={preview.schemaVersion} />
          <WorkbenchFact label="preview fingerprint" value={preview.previewFingerprint} />
          <WorkbenchFact
            label="candidate_publish_allowed"
            value={String(preview.candidatePublishAllowed)}
          />
          <WorkbenchFact
            label="production_write_allowed"
            value={String(preview.productionWriteAllowed)}
          />
        </div>
      </details>

      {selectedCandidate ? (
        <CandidateDetailDialog
          candidate={selectedCandidate}
          dialogRef={dialogRef}
          evidence={selectedEvidence}
          evidenceItems={preview.evidence.filter((item) =>
            selectedCandidate.evidenceRefs.includes(item.evidenceId),
          )}
          onClose={closeCandidate}
          onSelectEvidence={setSelectedEvidenceId}
        />
      ) : null}
    </div>
  );
}

function CandidateCard({
  candidate,
  onOpen,
}: {
  candidate: CapabilityDiscoveryCandidateAssertion;
  onOpen: (
    candidate: CapabilityDiscoveryCandidateAssertion,
    trigger: HTMLElement,
  ) => void;
}) {
  return (
    <article
      className="grid min-w-0 gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4"
      data-discovery-candidate-id={candidate.candidateId}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-[#B47767]">
            {platformLabels[candidate.platform]}
          </p>
          <h3 className="mt-1 text-base font-semibold text-[#2E201C]">
            {resourceLabels[candidate.resourceType]} · {operationLabels[candidate.operation]}
          </h3>
        </div>
        <WorkbenchTag tone="amber">待核验</WorkbenchTag>
      </div>
      <p className="break-all text-xs leading-5 text-[#7A625A]">
        {candidate.proposedImplementationId}
      </p>
      <div className="flex flex-wrap gap-2">
        <WorkbenchTag tone="rose">不可执行</WorkbenchTag>
        <WorkbenchTag tone="rose">不可发布</WorkbenchTag>
        <WorkbenchTag tone="neutral">
          {candidate.evidenceRefs.length} Evidence
        </WorkbenchTag>
      </div>
      <button
        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white outline-none transition hover:bg-[#B85F4F] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
        onClick={(event) => onOpen(candidate, event.currentTarget)}
        type="button"
      >
        审查 Candidate 证据
        <ChevronRight size={16} aria-hidden="true" />
      </button>
    </article>
  );
}

function CandidateDetailDialog({
  candidate,
  dialogRef,
  evidence,
  evidenceItems,
  onClose,
  onSelectEvidence,
}: {
  candidate: CapabilityDiscoveryCandidateAssertion;
  dialogRef: React.RefObject<HTMLElement | null>;
  evidence: CapabilityDiscoveryEvidence | null;
  evidenceItems: CapabilityDiscoveryEvidence[];
  onClose: () => void;
  onSelectEvidence: (evidenceId: string) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[#2E201C]/35 backdrop-blur-[2px]">
      <button
        aria-label="关闭 Candidate 详情遮罩"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
        tabIndex={-1}
        type="button"
      />
      <aside
        aria-labelledby="candidate-detail-title"
        aria-modal="true"
        className="relative z-10 grid h-full w-full grid-rows-[auto_1fr] overflow-hidden border-l border-[#E8D4CB] bg-[#F7F0EB] shadow-[-24px_0_60px_rgba(46,32,28,0.18)] sm:max-w-2xl"
        ref={dialogRef}
        role="dialog"
      >
        <header className="flex items-start justify-between gap-4 border-b border-[#E8D4CB] bg-[#FFFDFC] px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase text-[#B47767]">
              Candidate 详情
            </p>
            <h2
              className="mt-1 break-all text-lg font-semibold text-[#2E201C]"
              id="candidate-detail-title"
            >
              {candidate.candidateId}
            </h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <WorkbenchTag tone="amber">待核验</WorkbenchTag>
              <WorkbenchTag tone="rose">不可执行</WorkbenchTag>
              <WorkbenchTag tone="rose">不可发布</WorkbenchTag>
            </div>
          </div>
          <button
            aria-label="关闭 Candidate 详情"
            autoFocus
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#E8D4CB] bg-white text-[#7A625A] outline-none transition hover:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
            onClick={onClose}
            type="button"
          >
            <X size={18} aria-hidden="true" />
            <span className="sr-only">关闭 Candidate 详情</span>
          </button>
        </header>
        <div className="min-w-0 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="grid gap-5">
            <section className="grid gap-3" aria-labelledby="candidate-facts-heading">
              <h3 className="font-semibold text-[#2E201C]" id="candidate-facts-heading">
                候选能力事实
              </h3>
              <div className="grid gap-3 sm:grid-cols-2">
                <WorkbenchFact label="平台" value={platformLabels[candidate.platform]} />
                <WorkbenchFact
                  label="能力"
                  value={`${resourceLabels[candidate.resourceType]} · ${operationLabels[candidate.operation]}`}
                />
                <WorkbenchFact label="Parser" value={candidate.parserId} />
                <WorkbenchFact
                  label="约束数"
                  value={String(candidate.claimedConstraints.length)}
                />
              </div>
            </section>

            <section className="grid gap-3" aria-labelledby="candidate-evidence-heading">
              <h3 className="font-semibold text-[#2E201C]" id="candidate-evidence-heading">
                Evidence 引用
              </h3>
              {evidenceItems.map((item) => (
                <button
                  aria-pressed={evidence?.evidenceId === item.evidenceId}
                  className="flex min-h-11 min-w-0 items-center justify-between gap-3 rounded-xl border border-[#E8D4CB] bg-white px-3 text-left text-sm font-semibold text-[#7D4F43] outline-none transition hover:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                  key={item.evidenceId}
                  onClick={() => onSelectEvidence(item.evidenceId)}
                  type="button"
                >
                  <span className="min-w-0 break-all">查看 Evidence · {item.evidenceId}</span>
                  <ChevronRight className="shrink-0" size={16} aria-hidden="true" />
                </button>
              ))}
            </section>

            {evidence ? (
              <section
                className="grid gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4"
                aria-labelledby="evidence-detail-heading"
              >
                <h3 className="font-semibold text-[#2E201C]" id="evidence-detail-heading">
                  Evidence 详情
                </h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <WorkbenchFact label="grade" value={evidence.evidenceGrade} />
                  <WorkbenchFact label="type" value={evidence.evidenceType} />
                  <WorkbenchFact label="observed" value={evidence.observedAt} />
                  <WorkbenchFact label="provider_call_attempted" value="false" />
                </div>
                <a
                  className="break-all text-sm font-semibold text-[#B85F4F] underline decoration-[#E6B9AB] underline-offset-4 outline-none focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                  href={evidence.sourceUrl}
                  rel="noreferrer"
                  target="_blank"
                >
                  查看公开来源文档
                </a>
              </section>
            ) : (
              <p className="rounded-xl border border-dashed border-[#D9C4BA] bg-[#FFFDFC] p-4 text-sm text-[#7A625A]">
                选择一条 Evidence 引用后查看来源、时间与证据等级。
              </p>
            )}

            <details className="rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 text-sm text-[#7A625A]">
              <summary className="cursor-pointer font-semibold text-[#7D4F43] outline-none focus-visible:ring-4 focus-visible:ring-[#F3D7CE]">
                高级 Candidate 契约
              </summary>
              <div className="mt-3 grid gap-3">
                <WorkbenchFact
                  label="fingerprint"
                  value={candidate.candidateFingerprint}
                />
                <WorkbenchFact
                  label="source claims"
                  value={candidate.sourceClaimRefs.join(", ")}
                />
              </div>
            </details>
          </div>
        </div>
      </aside>
    </div>
  );
}

function SourceFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-[#F0E1D9] bg-white px-3 py-2">
      <p className="font-semibold text-[#B47767]">{label}</p>
      <p className="mt-1 break-all text-[#3B2924]">{value}</p>
    </div>
  );
}

function keepFocusInsideDialog(
  event: KeyboardEvent,
  dialog: HTMLElement | null,
) {
  if (!dialog) {
    return;
  }
  const focusable = [...dialog.querySelectorAll<HTMLElement>(
    'a[href], button:not([disabled]), details > summary, [tabindex]:not([tabindex="-1"])',
  )];
  const first = focusable[0];
  const last = focusable.at(-1);
  if (!first || !last) {
    return;
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
