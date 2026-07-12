"use client";

import {
  AlertTriangle,
  ExternalLink,
  FileSearch,
  Loader2,
  ShieldCheck,
  X,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import {
  WorkbenchFact,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import { listApiMarketPresentationsByProviderId } from "@/lib/api-market-catalog";
import { getCapabilityImplementationDetail } from "@/lib/api/capabilities";
import {
  capabilityPlatformLabel,
  capabilityScoreKeys,
  capabilityStatusLabel,
} from "@/lib/capability-market";
import type {
  CapabilityAssertion,
  CapabilityImplementationDetail,
  CapabilityMatrixCell,
  CapabilityOperation,
  CapabilityResourceType,
  CapabilityStatus,
} from "@/types/capability";

type CapabilityDetailDrawerProps = {
  cell: CapabilityMatrixCell | null;
  implementationId: string | null;
  evidenceLevel: string;
  generatedAt: string;
  returnFocusTo: HTMLElement | null;
  onClose: () => void;
};

const statusPriority: CapabilityStatus[] = [
  "verified",
  "partial",
  "candidate",
  "blocked",
  "unsupported",
  "deprecated",
  "unknown",
];

export function CapabilityDetailDrawer({
  cell,
  evidenceLevel,
  generatedAt,
  implementationId,
  onClose,
  returnFocusTo,
}: CapabilityDetailDrawerProps) {
  const [chosenImplementationId, setChosenImplementationId] = useState<
    string | null
  >(null);
  const [detail, setDetail] =
    useState<CapabilityImplementationDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const dialogRef = useRef<HTMLElement>(null);
  const open = cell !== null || implementationId !== null;
  const cellImplementationIds = cell?.implementationIds ?? [];
  const validChosenImplementationId =
    chosenImplementationId &&
    cellImplementationIds.includes(chosenImplementationId)
      ? chosenImplementationId
      : null;
  const requestedId =
    implementationId ??
    validChosenImplementationId ??
    (cellImplementationIds.length === 1 ? cellImplementationIds[0] : null);
  const selectionKey = `${implementationId ?? "cell"}:${cell?.platform ?? "none"}:${
    cell?.accessChannel ?? "none"
  }:${cellImplementationIds.join("|")}`;

  useEffect(() => {
    setChosenImplementationId(null);
    setDetail(null);
    setDetailError(null);
    setLoading(false);
  }, [selectionKey]);

  useEffect(() => {
    if (!open || requestedId === null) {
      setDetail(null);
      setDetailError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setDetail(null);
    setDetailError(null);
    setLoading(true);
    void getCapabilityImplementationDetail(requestedId)
      .then((nextDetail) => {
        if (!cancelled) {
          setDetail(nextDetail);
          setLoading(false);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setDetailError(
            cause instanceof Error
              ? cause.message
              : "capability_detail_unavailable",
          );
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [open, requestedId]);

  useEffect(() => {
    if (!open) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        requestAnimationFrame(() => returnFocusTo?.focus());
      } else if (event.key === "Tab") {
        keepFocusInsideDialog(event, dialogRef.current);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open, returnFocusTo]);

  if (!open) {
    return null;
  }

  function closeAndRestoreFocus() {
    onClose();
    requestAnimationFrame(() => returnFocusTo?.focus());
  }

  const assertions = detail?.assertions ?? [];
  const status = detail
    ? selectStatus(assertions)
    : cell?.summaryStatus ?? "unknown";
  const resourceTypes = detail
    ? unique(assertions.map((assertion) => assertion.resource_type))
    : cell?.resourceTypes ?? [];
  const operations = detail
    ? unique(assertions.map((assertion) => assertion.operation))
    : cell?.operations ?? [];
  const presentations = detail
    ? listApiMarketPresentationsByProviderId(
        detail.implementation.providerId,
      )
    : [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[#2E201C]/35 backdrop-blur-[2px]">
      <button
        aria-label="关闭能力详情遮罩"
        className="absolute inset-0 cursor-default"
        onClick={closeAndRestoreFocus}
        tabIndex={-1}
        type="button"
      />
      <aside
        aria-label="能力详情"
        aria-modal="true"
        className="relative z-10 grid h-full w-full grid-rows-[auto_1fr] overflow-hidden border-l border-[#E8D4CB] bg-[#F7F0EB] shadow-[-24px_0_60px_rgba(46,32,28,0.18)] sm:max-w-2xl xl:max-w-3xl"
        ref={dialogRef}
        role="dialog"
      >
        <header className="flex items-start justify-between gap-4 border-b border-[#E8D4CB] bg-[#FFFDFC] px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#B47767]">
              Capability evidence drawer
            </p>
            <h2 className="mt-1 break-all text-xl font-semibold text-[#2E201C]">
              {requestedId ?? "尚无能力事实"}
            </h2>
            <div className="mt-2 flex flex-wrap gap-2">
              <WorkbenchTag
                tone={status === "verified" ? "green" : status === "candidate" ? "amber" : "muted"}
              >
                {capabilityStatusLabel(status)}
              </WorkbenchTag>
              <WorkbenchTag tone="neutral">{evidenceLevel}</WorkbenchTag>
              <WorkbenchTag tone="rose">provider_call=false</WorkbenchTag>
            </div>
          </div>
          <button
            aria-label="关闭能力详情"
            autoFocus
            className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[#E8D4CB] bg-white text-[#7A625A] outline-none transition hover:border-[#C96F5C] hover:text-[#B85F4F] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
            onClick={closeAndRestoreFocus}
            type="button"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>

        <div className="min-w-0 overflow-y-auto px-4 py-5 sm:px-6">
          <div className="grid gap-5">
            <section aria-labelledby="boundary-heading" className="grid gap-3">
              <SectionHeading
                icon={ShieldCheck}
                id="boundary-heading"
                title="执行边界"
              />
              <div className="grid gap-2 sm:grid-cols-2">
                <WorkbenchFact label="generated" value={generatedAt} />
                <WorkbenchFact label="provider_call" value="false" />
                <WorkbenchFact label="production_write_allowed" value="false" />
                <WorkbenchFact label="credential_read_attempted" value="false" />
                <WorkbenchFact label="live_client_created" value="false" />
              </div>
            </section>

            <section aria-labelledby="scope-heading" className="grid gap-3">
              <SectionHeading
                icon={FileSearch}
                id="scope-heading"
                title="资源与操作范围"
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <TagSection
                  emptyText="无资源事实"
                  label="Resource"
                  values={resourceTypes}
                />
                <TagSection
                  emptyText="无操作事实"
                  label="Operation"
                  values={operations}
                />
              </div>
            </section>

            {cellImplementationIds.length > 1 ? (
              <label className="grid gap-2 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 text-sm font-semibold text-[#3B2924]">
                选择实现
                <select
                  className="h-11 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none focus-visible:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                  onChange={(event) =>
                    setChosenImplementationId(event.target.value || null)
                  }
                  value={validChosenImplementationId ?? ""}
                >
                  <option value="">请选择一个实现</option>
                  {cellImplementationIds.map((candidateId) => (
                    <option key={candidateId} value={candidateId}>
                      {candidateId}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}

            {requestedId === null ? (
              <section className="rounded-2xl border border-dashed border-[#D9C4BA] bg-[#FFFDFC] p-6 text-center">
                <p className="font-semibold text-[#3B2924]">
                  {cellImplementationIds.length === 0
                    ? "该单元尚无能力事实"
                    : "请选择一个实现后查看证据"}
                </p>
                <p className="mt-2 text-sm leading-6 text-[#7A625A]">
                  未发起 implementation detail 请求，也未把 unknown 推断为 unsupported。
                </p>
              </section>
            ) : null}

            {loading ? (
              <p
                className="inline-flex min-h-24 items-center justify-center gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-5 text-sm font-semibold text-[#7A625A]"
                role="status"
              >
                <Loader2 className="animate-spin" size={18} aria-hidden="true" />
                正在加载 implementation detail…
              </p>
            ) : null}

            {detailError ? (
              <p
                className="inline-flex items-start gap-2 rounded-2xl border border-[#FFD0C8] bg-[#FFF1EC] p-4 text-sm font-semibold text-[#B85F4F]"
                role="alert"
              >
                <AlertTriangle className="mt-0.5 shrink-0" size={16} aria-hidden="true" />
                {detailError} · 未使用静态 detail 回退
              </p>
            ) : null}

            {detail ? (
              <>
                <section aria-labelledby="implementation-heading" className="grid gap-3">
                  <SectionHeading
                    icon={FileSearch}
                    id="implementation-heading"
                    title="Implementation"
                  />
                  <div className="grid gap-2 sm:grid-cols-2">
                    <WorkbenchFact
                      label="implementation"
                      value={detail.implementation.implementationId}
                    />
                    <WorkbenchFact
                      label="provider"
                      value={detail.implementation.providerId}
                    />
                    <WorkbenchFact
                      label="platform"
                      value={capabilityPlatformLabel(
                        detail.implementation.platform,
                      )}
                    />
                    <WorkbenchFact
                      label="access channel"
                      value={detail.implementation.accessChannel}
                    />
                    <WorkbenchFact
                      label="deployment"
                      value={detail.implementation.deploymentMode}
                    />
                    <WorkbenchFact
                      label="api version"
                      value={detail.implementation.apiVersion}
                    />
                  </div>
                </section>

                <section aria-labelledby="blocked-heading" className="grid gap-3">
                  <SectionHeading
                    icon={AlertTriangle}
                    id="blocked-heading"
                    title="Blocked actions 与约束"
                  />
                  <TagSection
                    emptyText="无 blocked action 事实"
                    label="Blocked actions"
                    values={detail.implementation.blockedActions}
                  />
                  <div className="grid gap-2">
                    {detail.assertions.flatMap((assertion) =>
                      assertion.constraints.map((constraint) => (
                        <div
                          className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 text-sm"
                          key={`${assertion.assertion_id}:${constraint.code}`}
                        >
                          <p className="font-semibold text-[#3B2924]">
                            {constraint.code}
                          </p>
                          <p className="mt-1 text-xs text-[#7A625A]">
                            {constraint.severity} · {constraint.constraint_type}
                          </p>
                        </div>
                      )),
                    )}
                  </div>
                </section>

                <section aria-labelledby="scores-heading" className="grid gap-3">
                  <SectionHeading
                    icon={FileSearch}
                    id="scores-heading"
                    title="Capability scores"
                  />
                  <div className="grid gap-3">
                    {detail.assertions.map((assertion) => (
                      <article
                        className="rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4"
                        key={assertion.assertion_id}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="break-all text-sm font-semibold text-[#2E201C]">
                              {assertion.assertion_id}
                            </p>
                            <p className="mt-1 text-xs text-[#7A625A]">
                              {assertion.resource_type} · {assertion.operation}
                            </p>
                          </div>
                          <WorkbenchTag tone="amber">
                            {capabilityStatusLabel(assertion.support_status)}
                          </WorkbenchTag>
                        </div>
                        <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                          {capabilityScoreKeys.map((scoreKey) => (
                            <div
                              className="rounded-xl border border-[#F0E1D9] bg-white p-2"
                              key={scoreKey}
                            >
                              <dt className="break-words text-[10px] font-semibold uppercase text-[#B47767]">
                                {scoreKey}
                              </dt>
                              <dd className="mt-1 text-sm font-semibold text-[#2E201C]">
                                {String(assertion.score_profile[scoreKey] ?? "not provided")}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      </article>
                    ))}
                  </div>
                </section>

                <section aria-labelledby="evidence-heading" className="grid gap-3">
                  <SectionHeading
                    icon={ExternalLink}
                    id="evidence-heading"
                    title="Evidence"
                  />
                  <div className="grid gap-2">
                    {detail.evidence.map((evidence) => (
                      <a
                        className="grid min-w-0 gap-1 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] p-3 outline-none transition hover:border-[#C96F5C] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                        href={evidence.source_url}
                        key={evidence.evidence_id}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <span className="inline-flex items-center gap-2 break-all text-sm font-semibold text-[#7D4F43]">
                          {evidence.evidence_id}
                          <ExternalLink className="shrink-0" size={13} aria-hidden="true" />
                        </span>
                        <span className="break-all text-xs text-[#7A625A]">
                          {evidence.evidence_grade} · {evidence.hash_scope}
                        </span>
                      </a>
                    ))}
                  </div>
                </section>

                <section aria-labelledby="fixture-review-heading" className="grid gap-3">
                  <SectionHeading
                    icon={FileSearch}
                    id="fixture-review-heading"
                    title="Fixture Review"
                  />
                  {presentations.length > 0 ? (
                    <div className="grid gap-2 sm:grid-cols-2">
                      {presentations.map((presentation) => (
                        <Link
                          className="inline-flex min-h-11 items-center justify-between gap-3 rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 text-sm font-semibold text-[#7D4F43] outline-none transition hover:border-[#C96F5C] hover:bg-[#FFF1EC] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                          href={`/api-market/${presentation.id}` as Route}
                          key={presentation.id}
                        >
                          <span>Fixture Review: {presentation.title}</span>
                          <ExternalLink size={14} aria-hidden="true" />
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="rounded-xl border border-dashed border-[#D9C4BA] bg-[#FFFDFC] p-4 text-sm font-semibold text-[#7A625A]">
                      无展示增强；仅显示规范能力事实
                    </p>
                  )}
                </section>
              </>
            ) : null}
          </div>
        </div>
      </aside>
    </div>
  );
}

function SectionHeading({
  icon: Icon,
  id,
  title,
}: {
  icon: typeof FileSearch;
  id: string;
  title: string;
}) {
  return (
    <h3
      className="inline-flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.14em] text-[#B47767]"
      id={id}
    >
      <Icon size={15} aria-hidden="true" />
      {title}
    </h3>
  );
}

function TagSection({
  emptyText,
  label,
  values,
}: {
  emptyText: string;
  label: string;
  values: readonly string[];
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4">
      <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {values.length > 0 ? (
          values.map((value) => (
            <WorkbenchTag key={value} tone="muted">
              {value}
            </WorkbenchTag>
          ))
        ) : (
          <span className="text-sm font-semibold text-[#7A625A]">
            {emptyText}
          </span>
        )}
      </div>
    </div>
  );
}

function selectStatus(assertions: CapabilityAssertion[]): CapabilityStatus {
  for (const status of statusPriority) {
    if (assertions.some((assertion) => assertion.support_status === status)) {
      return status;
    }
  }
  return "unknown";
}

function unique<Value extends CapabilityResourceType | CapabilityOperation>(
  values: Value[],
): Value[] {
  return [...new Set(values)];
}

function keepFocusInsideDialog(
  event: KeyboardEvent,
  dialog: HTMLElement | null,
) {
  if (!dialog) {
    return;
  }
  const focusableElements = getFocusableElements(dialog);
  const first = focusableElements[0];
  const last = focusableElements.at(-1);
  if (!first || !last) {
    event.preventDefault();
    dialog.focus();
    return;
  }
  const activeElement = document.activeElement;
  if (!dialog.contains(activeElement)) {
    event.preventDefault();
    first.focus();
  } else if (event.shiftKey && activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), select:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hasAttribute("hidden"));
}
