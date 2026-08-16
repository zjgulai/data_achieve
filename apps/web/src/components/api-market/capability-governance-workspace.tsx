"use client";

import {
  CheckCircle2,
  FileCheck2,
  History,
  Loader2,
  LockKeyhole,
  RotateCcw,
  Send,
  ShieldCheck,
  X,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  WorkbenchFact,
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import {
  buildCapabilityGovernancePublicationRequest,
  buildCapabilityGovernanceReviewRequest,
  buildCapabilityGovernanceRollbackRequest,
  capabilityGovernanceTransport,
  type CapabilityGovernanceTransport,
} from "@/lib/api/capability-governance";
import { mockApiEnabled } from "@/lib/api/client";
import { buildMockCapabilityGovernanceCanonicalBundleDto } from "@/lib/capability-governance-mock";
import type { CapabilityImplementationDto } from "@/types/capability";
import type {
  CapabilityGovernanceCandidate,
  CapabilityGovernanceCandidateDetail,
  CapabilityGovernanceCandidateList,
  CapabilityGovernanceCanonicalAssertionDto,
  CapabilityGovernancePublicationList,
  CapabilityGovernancePublicationRevision,
  CapabilityGovernanceVerificationTask,
  CapabilityGovernanceVerificationTaskList,
} from "@/types/capability-governance";

type CanonicalBundle = {
  implementation: CapabilityImplementationDto;
  assertion: CapabilityGovernanceCanonicalAssertionDto;
};

type CapabilityGovernanceWorkspaceProps = {
  transport?: CapabilityGovernanceTransport;
  resolveCanonicalBundle?: (
    candidate: CapabilityGovernanceCandidate,
  ) => CanonicalBundle | null;
};

type GovernanceSnapshot = {
  candidates: {
    permissions: {
      canRead: boolean;
      canReview: boolean;
      canPublish: boolean;
    };
    items: CapabilityGovernanceCandidate[];
  };
  tasks: { items: CapabilityGovernanceVerificationTask[] };
  publications: {
    items: CapabilityGovernancePublicationRevision[];
    currentRevisionId: string | null;
  };
};

const GOVERNANCE_PAGE_LIMIT = 100;
const conflictCodes = new Set([
  "verification_task_conflict",
  "publication_parent_conflict",
]);

function defaultCanonicalBundleResolver(
  candidate: CapabilityGovernanceCandidate,
): CanonicalBundle | null {
  if (!mockApiEnabled) return null;
  const bundle = buildMockCapabilityGovernanceCanonicalBundleDto();
  const assertion = candidate.candidateAssertion;
  if (
    bundle.implementation.platform !== assertion.platform ||
    bundle.implementation.access_channel !== assertion.accessChannel ||
    bundle.assertion.resource_type !== assertion.resourceType ||
    bundle.assertion.operation !== assertion.operation
  ) {
    return null;
  }
  return bundle;
}

async function readGovernanceSnapshot(
  transport: CapabilityGovernanceTransport,
): Promise<GovernanceSnapshot> {
  const [candidatePages, taskPages, publicationPages] = await Promise.all([
    readAllGovernancePages<
      CapabilityGovernanceCandidate,
      CapabilityGovernanceCandidateList
    >((options) => transport.listCandidates(options)),
    readAllGovernancePages<
      CapabilityGovernanceVerificationTask,
      CapabilityGovernanceVerificationTaskList
    >((options) => transport.listVerificationTasks(options)),
    readAllGovernancePages<
      CapabilityGovernancePublicationRevision,
      CapabilityGovernancePublicationList
    >((options) => transport.listPublications(options)),
  ]);
  const candidatePage = candidatePages.first;
  const publicationPage = publicationPages.first;
  if (!candidatePage || !publicationPage) {
    throw new Error("capability_governance_pagination_invalid");
  }
  if (
    publicationPages.pages.some(
      (page) => page.currentRevisionId !== publicationPage.currentRevisionId,
    )
  ) {
    throw new Error("capability_governance_pagination_invalid");
  }
  return {
    candidates: {
      permissions: candidatePage.permissions,
      items: latestCandidateVersions(candidatePages.items),
    },
    tasks: { items: taskPages.items },
    publications: {
      items: publicationPages.items,
      currentRevisionId: publicationPage.currentRevisionId,
    },
  };
}

async function readAllGovernancePages<
  Item,
  Page extends { items: Item[]; limit: number; offset: number },
>(
  load: (options: { limit: number; offset: number }) => Promise<Page>,
): Promise<{ first: Page | null; items: Item[]; pages: Page[] }> {
  const items: Item[] = [];
  const pages: Page[] = [];
  let offset = 0;
  while (true) {
    const page = await load({ limit: GOVERNANCE_PAGE_LIMIT, offset });
    if (
      page.limit !== GOVERNANCE_PAGE_LIMIT ||
      page.offset !== offset ||
      page.items.length > GOVERNANCE_PAGE_LIMIT
    ) {
      throw new Error("capability_governance_pagination_invalid");
    }
    pages.push(page);
    items.push(...page.items);
    if (page.items.length < GOVERNANCE_PAGE_LIMIT) break;
    offset += page.items.length;
  }
  return { first: pages[0] ?? null, items, pages };
}

function latestCandidateVersions(
  candidates: CapabilityGovernanceCandidate[],
): CapabilityGovernanceCandidate[] {
  const latest = new Map<string, CapabilityGovernanceCandidate>();
  for (const candidate of candidates) {
    const existing = latest.get(candidate.candidateKey);
    if (!existing || candidate.semanticVersion > existing.semanticVersion) {
      latest.set(candidate.candidateKey, candidate);
    }
  }
  return [...latest.values()];
}

function errorCode(cause: unknown): string {
  if (cause instanceof Error) {
    const candidate = cause as Error & { code?: unknown };
    return typeof candidate.code === "string" && candidate.code.length > 0
      ? candidate.code
      : cause.message;
  }
  return "capability_governance_unavailable";
}

function formatToken(value: string): string {
  return value.replaceAll("_", " ");
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}

export function CapabilityGovernanceWorkspace({
  transport = capabilityGovernanceTransport,
  resolveCanonicalBundle = defaultCanonicalBundleResolver,
}: CapabilityGovernanceWorkspaceProps) {
  const [snapshot, setSnapshot] = useState<GovernanceSnapshot | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedCandidateKey, setSelectedCandidateKey] = useState<
    string | null
  >(null);
  const [detail, setDetail] =
    useState<CapabilityGovernanceCandidateDetail | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(
    null,
  );
  const [detailLoading, setDetailLoading] = useState(false);
  const [mutationBusy, setMutationBusy] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [reason, setReason] = useState(
    "Evidence 与 canonical contract 已完成人工复核。",
  );
  const returnFocusToRef = useRef<HTMLElement | null>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const idempotencySequence = useRef(0);
  const refreshSequenceRef = useRef(0);
  const selectedCandidateKeyRef = useRef<string | null>(null);
  selectedCandidateKeyRef.current = selectedCandidateKey;

  const permissions = snapshot?.candidates.permissions ?? null;
  const canonicalBundle = useMemo(
    () => (detail ? resolveCanonicalBundle(detail.candidate) : null),
    [detail, resolveCanonicalBundle],
  );
  const selectedEvidence = useMemo(
    () =>
      detail?.evidence.find(
        (evidence) => evidence.evidence_id === selectedEvidenceId,
      ) ?? null,
    [detail, selectedEvidenceId],
  );

  const applyDetail = useCallback(
    (nextDetail: CapabilityGovernanceCandidateDetail | null) => {
      setDetail(nextDetail);
      setSelectedEvidenceId((current) => {
        if (
          current &&
          nextDetail?.evidence.some(
            (evidence) => evidence.evidence_id === current,
          )
        ) {
          return current;
        }
        return nextDetail?.evidence[0]?.evidence_id ?? null;
      });
    },
    [],
  );

  const refreshAuthoritativeState = useCallback(
    async (candidateKey: string | null) => {
      const refreshSequence = ++refreshSequenceRef.current;
      const [nextSnapshot, nextDetail] = await Promise.all([
        readGovernanceSnapshot(transport),
        candidateKey
          ? transport.getCandidate(candidateKey)
          : Promise.resolve(null),
      ]);
      if (refreshSequence !== refreshSequenceRef.current) return;
      setSnapshot(nextSnapshot);
      if (candidateKey === selectedCandidateKeyRef.current) {
        applyDetail(nextDetail);
      }
    },
    [applyDetail, transport],
  );

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    void readGovernanceSnapshot(transport)
      .then((nextSnapshot) => {
        if (!cancelled) setSnapshot(nextSnapshot);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setLoadError(errorCode(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [transport]);

  useEffect(() => {
    if (!selectedCandidateKey) {
      applyDetail(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setMutationError(null);
    void transport
      .getCandidate(selectedCandidateKey)
      .then((nextDetail) => {
        if (!cancelled) applyDetail(nextDetail);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setMutationError(errorCode(cause));
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyDetail, selectedCandidateKey, transport]);

  function closeDetail() {
    selectedCandidateKeyRef.current = null;
    setSelectedCandidateKey(null);
    applyDetail(null);
    const restoreFocus = () => returnFocusToRef.current?.focus();
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(restoreFocus);
    } else {
      setTimeout(restoreFocus, 0);
    }
  }

  useEffect(() => {
    if (!detail) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDetail();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  });

  function nextIdempotencyKey(scope: string): string {
    idempotencySequence.current += 1;
    return `governance-ui-${scope}-${Date.now()}-${idempotencySequence.current}`;
  }

  async function recoverFromMutationError(cause: unknown) {
    const code = errorCode(cause);
    if (!conflictCodes.has(code)) {
      setMutationError(code);
      return;
    }
    try {
      await refreshAuthoritativeState(selectedCandidateKey);
      setMutationError(`${code} · 已重新加载权威状态`);
    } catch (refreshCause: unknown) {
      setMutationError(
        `${code} · 权威状态重载失败：${errorCode(refreshCause)}`,
      );
    }
  }

  async function review(action: "verify" | "reject") {
    const task = detail?.openVerificationTask;
    if (!detail || !task || !permissions?.canReview) return;
    if (action === "verify" && !canonicalBundle) {
      setMutationError("canonical_review_bundle_unavailable");
      return;
    }
    setMutationBusy(action);
    setMutationError(null);
    setStatusMessage(null);
    try {
      const payload =
        action === "reject"
          ? buildCapabilityGovernanceReviewRequest({
              action,
              expectedTaskVersion: task.taskVersion,
              reason,
            })
          : buildCapabilityGovernanceReviewRequest({
              action,
              expectedTaskVersion: task.taskVersion,
              reason,
              canonicalImplementation: canonicalBundle!.implementation,
              canonicalAssertion: canonicalBundle!.assertion,
            });
      const response = await transport.reviewCandidate(
        task.id,
        payload,
        nextIdempotencyKey(`review-${task.id}`),
      );
      await refreshAuthoritativeState(selectedCandidateKey);
      setStatusMessage(
        response.verificationStatus === "verified"
          ? "核验已记录；Candidate 仍需独立发布后才进入 Catalog。"
          : "拒绝决定已记录；Candidate 未进入 Catalog。",
      );
    } catch (cause: unknown) {
      await recoverFromMutationError(cause);
    } finally {
      setMutationBusy(null);
    }
  }

  async function publishVerifiedDecision() {
    const decision = detail?.latestDecision;
    if (
      !decision ||
      decision.verificationStatus !== "verified" ||
      !permissions?.canPublish ||
      !snapshot
    ) {
      return;
    }
    setMutationBusy("publish");
    setMutationError(null);
    setStatusMessage(null);
    try {
      const response = await transport.publishCatalog(
        buildCapabilityGovernancePublicationRequest({
          expectedParentRevisionId: snapshot.publications.currentRevisionId,
          reason,
          operations: [
            {
              operation: "upsert_verified_assertion",
              verificationDecisionId: decision.id,
            },
          ],
        }),
        nextIdempotencyKey(`publish-${decision.id}`),
      );
      await refreshAuthoritativeState(selectedCandidateKey);
      setStatusMessage(`Revision #${response.revisionNumber} 已发布。`);
    } catch (cause: unknown) {
      await recoverFromMutationError(cause);
    } finally {
      setMutationBusy(null);
    }
  }

  async function rollbackTo(revision: CapabilityGovernancePublicationRevision) {
    const currentRevisionId = snapshot?.publications.currentRevisionId;
    if (!currentRevisionId || revision.isCurrent || !permissions?.canPublish) {
      return;
    }
    setMutationBusy(`rollback-${revision.id}`);
    setMutationError(null);
    setStatusMessage(null);
    try {
      const response = await transport.rollbackCatalog(
        buildCapabilityGovernanceRollbackRequest({
          expectedCurrentRevisionId: currentRevisionId,
          targetRevisionId: revision.id,
          reason,
        }),
        nextIdempotencyKey(`rollback-${revision.id}`),
      );
      await refreshAuthoritativeState(selectedCandidateKey);
      setStatusMessage(
        `Revision #${response.revisionNumber} 已回滚到 Revision #${revision.revisionNumber}。`,
      );
    } catch (cause: unknown) {
      await recoverFromMutationError(cause);
    } finally {
      setMutationBusy(null);
    }
  }

  if (loadError) {
    return (
      <section
        className="border-t border-[#E8D4CB] pt-8"
        aria-labelledby="governance-heading"
      >
        <div
          className="rounded-2xl border border-[#F0B9AD] bg-[#FFF1EC] p-5 text-sm text-[#7D4F43]"
          role="alert"
        >
          <p className="font-semibold" id="governance-heading">
            治理工作台不可用
          </p>
          <p className="mt-2 break-all">{loadError}</p>
          <p className="mt-2">未使用 mock 数据回退，也未执行任何写入。</p>
        </div>
      </section>
    );
  }

  if (!snapshot) {
    return (
      <section
        className="border-t border-[#E8D4CB] pt-8"
        aria-label="治理工作台加载中"
      >
        <div className="flex min-h-32 items-center justify-center gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] text-sm text-[#7A625A]">
          <Loader2 className="animate-spin" size={18} aria-hidden="true" />
          正在读取治理账本
        </div>
      </section>
    );
  }

  const openTaskCount = snapshot.tasks.items.filter(
    (task) => task.status === "open",
  ).length;

  return (
    <section
      aria-labelledby="governance-heading"
      className="grid gap-5 border-t border-[#E8D4CB] pt-8"
    >
      <header className="grid gap-4 rounded-[1.75rem] border border-[#E1C8BC] bg-[#382822] px-5 py-6 text-white shadow-[0_24px_70px_rgba(56,40,34,0.18)] sm:px-7 lg:grid-cols-[1fr_auto] lg:items-end">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#E8B9A9]">
            Route B · Review / Publish / Rollback
          </p>
          <h2
            className="mt-2 text-2xl font-semibold tracking-[-0.02em]"
            id="governance-heading"
          >
            治理审计台
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#E8D4CB]">
            Candidate、Evidence、人工决定与 Catalog Revision
            分层留痕；核验不等于发布，发布不等于生产验收。
          </p>
        </div>
        <div className="flex flex-wrap gap-2 lg:justify-end">
          {!permissions?.canReview && !permissions?.canPublish ? (
            <WorkbenchTag tone="amber">只读访问</WorkbenchTag>
          ) : null}
          <WorkbenchTag tone={permissions?.canReview ? "green" : "muted"}>
            {permissions?.canReview ? "可审查" : "不可审查"}
          </WorkbenchTag>
          <WorkbenchTag tone={permissions?.canPublish ? "green" : "muted"}>
            {permissions?.canPublish ? "可发布" : "不可发布"}
          </WorkbenchTag>
          <WorkbenchTag tone="rose">production unchanged</WorkbenchTag>
        </div>
      </header>

      {statusMessage ? (
        <p
          aria-live="polite"
          className="rounded-xl border border-[#B9DEC4] bg-[#EAF8EE] px-4 py-3 text-sm font-semibold text-[#257B42]"
          role="status"
        >
          {statusMessage}
        </p>
      ) : null}
      {mutationError ? (
        <p
          className="rounded-xl border border-[#F0B9AD] bg-[#FFF1EC] px-4 py-3 text-sm font-semibold text-[#9B4637]"
          role="alert"
        >
          {mutationError}
        </p>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.75fr)]">
        <WorkbenchPanel
          action={
            <WorkbenchTag tone="amber">{openTaskCount} open</WorkbenchTag>
          }
          icon={FileCheck2}
          label="Review queue"
          subtitle="按业务事实优先审查；fingerprint 与 schema 默认折叠。"
          title="Candidate Inbox"
        >
          <div className="grid gap-1">
            {snapshot.candidates.items.map((candidate, index) => (
              <article
                className="group grid min-w-0 grid-cols-[2.5rem_minmax(0,1fr)_auto] items-center gap-3 border-b border-[#F0E1D9] py-4 last:border-b-0"
                data-governance-candidate-key={candidate.candidateKey}
                key={candidate.id}
              >
                <span className="font-mono text-sm text-[#C49A8C]">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-[#2E201C]">
                      {formatToken(candidate.candidateAssertion.resourceType)} ·{" "}
                      {formatToken(candidate.candidateAssertion.operation)}
                    </p>
                    <WorkbenchTag tone="amber">待审查</WorkbenchTag>
                  </div>
                  <p className="mt-1 truncate text-sm text-[#7A625A]">
                    {formatToken(candidate.candidateAssertion.platform)} /{" "}
                    {candidate.proposedImplementation.sourceLabel}
                  </p>
                </div>
                <button
                  className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-[#E0C7BB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#7D4F43] outline-none transition hover:border-[#C96F5C] hover:bg-[#FFF1EC] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                  onClick={(event) => {
                    returnFocusToRef.current = event.currentTarget;
                    selectedCandidateKeyRef.current = candidate.candidateKey;
                    setSelectedCandidateKey(candidate.candidateKey);
                  }}
                  type="button"
                >
                  审查档案
                  <ShieldCheck size={16} aria-hidden="true" />
                </button>
              </article>
            ))}
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel
          action={
            <WorkbenchTag
              tone={snapshot.publications.currentRevisionId ? "green" : "muted"}
            >
              {snapshot.publications.currentRevisionId
                ? "Head ready"
                : "No Head"}
            </WorkbenchTag>
          }
          icon={History}
          label="Append-only history"
          subtitle="每次 publish / rollback 都创建新 Revision。"
          title="Revision Ledger"
        >
          {snapshot.publications.items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[#D9C4BA] bg-[#FFFDFC] p-5 text-sm leading-6 text-[#7A625A]">
              <LockKeyhole
                className="mb-3 text-[#B47767]"
                size={20}
                aria-hidden="true"
              />
              尚无 Catalog Revision。只有已核验 Decision 才能进入发布步骤。
            </div>
          ) : (
            <ol className="relative grid gap-4 before:absolute before:bottom-3 before:left-[0.55rem] before:top-3 before:w-px before:bg-[#E2C8BC]">
              {snapshot.publications.items.map((revision) => (
                <li
                  className="relative grid grid-cols-[1.2rem_minmax(0,1fr)] gap-3"
                  data-governance-revision-id={revision.id}
                  key={revision.id}
                >
                  <span className="relative z-10 mt-1 h-3 w-3 rounded-full border-2 border-[#FFFDFC] bg-[#C96F5C] shadow-[0_0_0_1px_#C96F5C]" />
                  <div className="min-w-0 rounded-xl bg-[#FFFDFC] p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold text-[#2E201C]">
                        Revision #{revision.revisionNumber}
                      </p>
                      {revision.isCurrent ? (
                        <WorkbenchTag tone="green">当前版本</WorkbenchTag>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[#7A625A]">
                      {formatTime(revision.publishedAt)} · {revision.reason}
                    </p>
                    {revision.restoredFromRevisionId ? (
                      <p className="mt-2 break-all text-xs text-[#B85F4F]">
                        restored_from: {revision.restoredFromRevisionId}
                      </p>
                    ) : null}
                    {!revision.isCurrent && permissions?.canPublish ? (
                      <button
                        className="mt-3 inline-flex min-h-10 items-center gap-2 rounded-lg border border-[#E0C7BB] px-3 text-xs font-semibold text-[#7D4F43] outline-none hover:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE] disabled:cursor-wait disabled:opacity-60"
                        disabled={mutationBusy !== null}
                        onClick={() => void rollbackTo(revision)}
                        type="button"
                      >
                        <RotateCcw size={14} aria-hidden="true" />
                        回滚到 Revision #{revision.revisionNumber}
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </WorkbenchPanel>
      </div>

      <div className="grid gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 text-sm text-[#7A625A] sm:grid-cols-3">
        <p>
          <strong className="text-[#2E201C]">database_write</strong>
          <br />
          仅在明确点击 review / publish / rollback 后发生。
        </p>
        <p>
          <strong className="text-[#2E201C]">provider_call=false</strong>
          <br />
          治理流程不触发 Provider、Actor、Browser 或 LLM。
        </p>
        <p>
          <strong className="text-[#2E201C]">证据层级</strong>
          <br />
          本页面状态不等同于 PostgreSQL migration 或生产验收。
        </p>
      </div>

      {selectedCandidateKey && detailLoading && !detail ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#2E201C]/35 backdrop-blur-[2px]">
          <div className="inline-flex items-center gap-3 rounded-2xl bg-white px-5 py-4 text-sm font-semibold text-[#7A625A] shadow-xl">
            <Loader2 className="animate-spin" size={18} aria-hidden="true" />
            正在读取 Candidate dossier
          </div>
        </div>
      ) : null}

      {detail ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-[#2E201C]/35 backdrop-blur-[2px]">
          <button
            aria-label="关闭治理档案遮罩"
            className="absolute inset-0 cursor-default"
            onClick={closeDetail}
            tabIndex={-1}
            type="button"
          />
          <aside
            aria-labelledby="governance-dossier-title"
            aria-modal="true"
            className="relative z-10 grid h-full w-full grid-rows-[auto_1fr] overflow-hidden border-l border-[#E8D4CB] bg-[#F7F0EB] shadow-[-24px_0_60px_rgba(46,32,28,0.18)] sm:max-w-3xl"
            ref={dialogRef}
            role="dialog"
          >
            <header className="flex items-start justify-between gap-4 border-b border-[#E8D4CB] bg-[#382822] px-4 py-5 text-white sm:px-6">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#E8B9A9]">
                  Evidence Dossier
                </p>
                <h2
                  className="mt-2 text-xl font-semibold"
                  id="governance-dossier-title"
                >
                  {formatToken(
                    detail.candidate.candidateAssertion.resourceType,
                  )}{" "}
                  · {formatToken(detail.candidate.candidateAssertion.operation)}
                </h2>
                <div className="mt-3 flex flex-wrap gap-2">
                  {detail.latestDecision ? (
                    <WorkbenchTag
                      tone={
                        detail.latestDecision.verificationStatus === "verified"
                          ? "green"
                          : "red"
                      }
                    >
                      {detail.latestDecision.verificationStatus === "verified"
                        ? "已核验"
                        : "已拒绝"}
                    </WorkbenchTag>
                  ) : (
                    <WorkbenchTag tone="amber">待决定</WorkbenchTag>
                  )}
                  <WorkbenchTag tone="rose">非执行入口</WorkbenchTag>
                </div>
              </div>
              <button
                aria-label="关闭治理档案"
                autoFocus
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/20 bg-white/10 text-white outline-none hover:bg-white/20 focus-visible:ring-4 focus-visible:ring-[#E8B9A9]/50"
                onClick={closeDetail}
                type="button"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </header>

            <div className="min-w-0 overflow-y-auto px-4 py-5 sm:px-6">
              <div className="grid gap-6">
                <section
                  className="grid gap-3"
                  aria-labelledby="governance-business-facts"
                >
                  <h3
                    className="font-semibold text-[#2E201C]"
                    id="governance-business-facts"
                  >
                    业务事实
                  </h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <WorkbenchFact
                      label="platform / channel"
                      value={`${formatToken(detail.candidate.candidateAssertion.platform)} / ${formatToken(detail.candidate.candidateAssertion.accessChannel)}`}
                    />
                    <WorkbenchFact
                      label="source"
                      value={
                        detail.candidate.proposedImplementation.sourceLabel
                      }
                    />
                    <WorkbenchFact
                      label="auth"
                      value={
                        detail.candidate.proposedImplementation.claimedAuthMode
                      }
                    />
                    <WorkbenchFact
                      label="semantic version"
                      value={String(detail.candidate.semanticVersion)}
                    />
                  </div>
                </section>

                <section
                  className="grid gap-3"
                  aria-labelledby="governance-evidence-list"
                >
                  <div className="flex items-center justify-between gap-3">
                    <h3
                      className="font-semibold text-[#2E201C]"
                      id="governance-evidence-list"
                    >
                      Evidence Dossier
                    </h3>
                    <WorkbenchTag tone="neutral">
                      {detail.evidence.length} items
                    </WorkbenchTag>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {detail.evidence.map((evidence) => (
                      <button
                        aria-pressed={
                          selectedEvidenceId === evidence.evidence_id
                        }
                        className="min-h-11 min-w-0 rounded-xl border border-[#E0C7BB] bg-[#FFFDFC] p-3 text-left outline-none transition hover:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE] aria-pressed:border-[#C96F5C] aria-pressed:bg-[#FFF1EC]"
                        data-governance-evidence-id={evidence.evidence_id}
                        key={evidence.evidence_id}
                        onClick={() =>
                          setSelectedEvidenceId(evidence.evidence_id)
                        }
                        type="button"
                      >
                        <span className="block text-xs font-semibold uppercase text-[#B47767]">
                          {evidence.evidence_grade}
                        </span>
                        <span className="mt-1 block truncate text-sm font-semibold text-[#2E201C]">
                          {evidence.source_version}
                        </span>
                      </button>
                    ))}
                  </div>
                  {selectedEvidence ? (
                    <div className="grid gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 sm:grid-cols-2">
                      <WorkbenchFact
                        label="observed"
                        value={formatTime(selectedEvidence.observed_at)}
                      />
                      <WorkbenchFact
                        label="type"
                        value={selectedEvidence.evidence_type}
                      />
                      <a
                        className="min-w-0 break-all text-sm font-semibold text-[#B85F4F] underline decoration-[#E6B9AB] underline-offset-4 outline-none focus-visible:ring-4 focus-visible:ring-[#F3D7CE] sm:col-span-2"
                        href={selectedEvidence.source_url}
                        rel="noreferrer"
                        target="_blank"
                      >
                        查看公开证据来源
                      </a>
                      <p className="text-xs text-[#7A625A] sm:col-span-2">
                        provider_call_attempted=false ·
                        credential_read_attempted=false ·
                        production_write_attempted=false
                      </p>
                    </div>
                  ) : null}
                </section>

                <details className="rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 text-sm text-[#7A625A]">
                  <summary className="cursor-pointer font-semibold text-[#7D4F43] outline-none focus-visible:ring-4 focus-visible:ring-[#F3D7CE]">
                    高级契约与指纹
                  </summary>
                  <div className="mt-4 grid gap-3">
                    <WorkbenchFact
                      label="candidate fingerprint"
                      value={detail.candidate.candidateFingerprint}
                    />
                    <WorkbenchFact
                      label="candidate key"
                      value={detail.candidate.candidateKey}
                    />
                    {selectedEvidence ? (
                      <WorkbenchFact
                        label="content hash"
                        value={selectedEvidence.content_hash}
                      />
                    ) : null}
                    <pre className="max-h-56 overflow-auto rounded-xl bg-[#2E201C] p-3 text-xs leading-5 text-[#F7E9E2]">
                      {JSON.stringify(
                        detail.candidate.candidateAssertion
                          .claimedFieldContract,
                        null,
                        2,
                      )}
                    </pre>
                  </div>
                </details>

                <section
                  className="grid gap-4 rounded-2xl border border-[#E1C8BC] bg-white p-4"
                  aria-labelledby="governance-decision-gate"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3
                        className="font-semibold text-[#2E201C]"
                        id="governance-decision-gate"
                      >
                        Reviewer / Publisher Gate
                      </h3>
                      <p className="mt-1 text-sm leading-6 text-[#7A625A]">
                        每次写入携带 expected version 与 Idempotency-Key；409
                        后重新加载权威状态。
                      </p>
                    </div>
                    {detail.openVerificationTask ? (
                      <WorkbenchTag tone="amber">
                        Task v{detail.openVerificationTask.taskVersion}
                      </WorkbenchTag>
                    ) : (
                      <WorkbenchTag tone="green">Task resolved</WorkbenchTag>
                    )}
                  </div>
                  {permissions?.canReview || permissions?.canPublish ? (
                    <label className="grid gap-2 text-sm font-semibold text-[#7D4F43]">
                      审计原因
                      <textarea
                        className="min-h-24 resize-y rounded-xl border border-[#E0C7BB] bg-[#FFFDFC] px-3 py-2 font-normal text-[#2E201C] outline-none focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                        onChange={(event) => setReason(event.target.value)}
                        value={reason}
                      />
                    </label>
                  ) : (
                    <p className="rounded-xl border border-dashed border-[#D9C4BA] bg-[#FFFDFC] p-4 text-sm text-[#7A625A]">
                      只读访问：可审阅 Evidence 与历史，但不能创建 Decision 或
                      Revision。
                    </p>
                  )}

                  {permissions?.canReview && detail.openVerificationTask ? (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <button
                        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#2F7D4B] px-4 text-sm font-semibold text-white outline-none hover:bg-[#25663D] focus-visible:ring-4 focus-visible:ring-[#B9DEC4] disabled:cursor-not-allowed disabled:opacity-55"
                        disabled={
                          !canonicalBundle ||
                          mutationBusy !== null ||
                          reason.trim().length === 0
                        }
                        onClick={() => void review("verify")}
                        title={
                          !canonicalBundle
                            ? "真实模式需要显式 canonical review bundle"
                            : undefined
                        }
                        type="button"
                      >
                        {mutationBusy === "verify" ? (
                          <Loader2
                            className="animate-spin"
                            size={16}
                            aria-hidden="true"
                          />
                        ) : (
                          <CheckCircle2 size={16} aria-hidden="true" />
                        )}
                        核验通过
                      </button>
                      <button
                        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-[#E0A99C] bg-[#FFF1EC] px-4 text-sm font-semibold text-[#9B4637] outline-none hover:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE] disabled:cursor-not-allowed disabled:opacity-55"
                        disabled={
                          mutationBusy !== null || reason.trim().length === 0
                        }
                        onClick={() => void review("reject")}
                        type="button"
                      >
                        {mutationBusy === "reject" ? (
                          <Loader2
                            className="animate-spin"
                            size={16}
                            aria-hidden="true"
                          />
                        ) : (
                          <XCircle size={16} aria-hidden="true" />
                        )}
                        拒绝 Candidate
                      </button>
                    </div>
                  ) : null}

                  {permissions?.canPublish &&
                  detail.latestDecision?.verificationStatus === "verified" ? (
                    <button
                      className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-[#C96F5C] px-4 text-sm font-semibold text-white outline-none hover:bg-[#B85F4F] focus-visible:ring-4 focus-visible:ring-[#F3D7CE] disabled:cursor-wait disabled:opacity-60"
                      disabled={
                        mutationBusy !== null || reason.trim().length === 0
                      }
                      onClick={() => void publishVerifiedDecision()}
                      type="button"
                    >
                      {mutationBusy === "publish" ? (
                        <Loader2
                          className="animate-spin"
                          size={16}
                          aria-hidden="true"
                        />
                      ) : (
                        <Send size={16} aria-hidden="true" />
                      )}
                      发布到 Catalog
                    </button>
                  ) : null}
                </section>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </section>
  );
}
