"use client";

import { ArrowUpRight, GitCompareArrows, ListChecks } from "lucide-react";
import { useState } from "react";

import {
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import {
  capabilityPlatformLabel,
  capabilityStatusLabel,
} from "@/lib/capability-market";
import type {
  CapabilityAssertion,
  CapabilityImplementation,
  CapabilityStatus,
} from "@/types/capability";

type CapabilityListViewProps = {
  assertions: CapabilityAssertion[];
  implementations: CapabilityImplementation[];
  evidenceLevel: string;
  onSelectImplementation: (
    implementationId: string,
    trigger: HTMLElement,
  ) => void;
  onCompare: (implementationIds: string[]) => Promise<void>;
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

export function CapabilityListView({
  assertions,
  evidenceLevel,
  implementations,
  onCompare,
  onSelectImplementation,
}: CapabilityListViewProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [comparisonPending, setComparisonPending] = useState(false);
  const implementationById = new Map(
    implementations.map((implementation) => [
      implementation.implementationId,
      implementation,
    ]),
  );
  const assertionsByImplementation = new Map<string, CapabilityAssertion[]>();
  for (const assertion of assertions) {
    const ownedAssertions =
      assertionsByImplementation.get(assertion.implementation_id) ?? [];
    ownedAssertions.push(assertion);
    assertionsByImplementation.set(assertion.implementation_id, ownedAssertions);
  }
  const platformCounts = new Map<string, number>();
  for (const implementation of implementations) {
    platformCounts.set(
      implementation.platform,
      (platformCounts.get(implementation.platform) ?? 0) + 1,
    );
  }
  const hasComparablePlatform = [...platformCounts.values()].some(
    (count) => count > 1,
  );
  const visibleSelectedIds = selectedIds.filter((implementationId) =>
    implementationById.has(implementationId),
  );
  const selectedPlatform = visibleSelectedIds[0]
    ? implementationById.get(visibleSelectedIds[0])?.platform
    : undefined;

  function toggleComparison(implementation: CapabilityImplementation) {
    setSelectedIds((current) => {
      const visibleCurrent = current.filter((implementationId) =>
        implementationById.has(implementationId),
      );
      if (visibleCurrent.includes(implementation.implementationId)) {
        return visibleCurrent.filter(
          (implementationId) =>
            implementationId !== implementation.implementationId,
        );
      }
      const currentPlatform = visibleCurrent[0]
        ? implementationById.get(visibleCurrent[0])?.platform
        : implementation.platform;
      if (
        visibleCurrent.length >= 3 ||
        currentPlatform !== implementation.platform
      ) {
        return visibleCurrent;
      }
      return [...visibleCurrent, implementation.implementationId];
    });
  }

  async function submitComparison() {
    setComparisonPending(true);
    try {
      await onCompare(visibleSelectedIds);
    } finally {
      setComparisonPending(false);
    }
  }

  return (
    <WorkbenchPanel
      action={
        <button
          aria-label="比较实现"
          className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white outline-none transition hover:bg-[#B85F4F] focus-visible:ring-4 focus-visible:ring-[#F3D7CE] disabled:cursor-not-allowed disabled:bg-[#D9C4BA]"
          disabled={
            comparisonPending ||
            visibleSelectedIds.length < 2 ||
            visibleSelectedIds.length > 3
          }
          onClick={() => void submitComparison()}
          type="button"
        >
          <GitCompareArrows size={16} aria-hidden="true" />
          {comparisonPending ? "正在比较…" : "比较实现"}
        </button>
      }
      icon={ListChecks}
      label="Implementation registry"
      subtitle="保持 API 输入顺序；比较仅允许同平台 2–3 个实现。"
      title="实现与证据列表"
    >
      {!hasComparablePlatform ? (
        <p className="mb-4 rounded-xl border border-[#F0E1D9] bg-[#FBF8F5] px-4 py-3 text-sm font-semibold text-[#7A625A]">
          当前平台只有一个实现，暂无可比较项
        </p>
      ) : (
        <p className="mb-4 text-xs font-semibold text-[#7A625A]">
          已选 {visibleSelectedIds.length}/3；切换平台前请清空当前选择。
        </p>
      )}

      {implementations.length > 0 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {implementations.map((implementation) => {
            const ownedAssertions =
              assertionsByImplementation.get(implementation.implementationId) ??
              [];
            const status = selectStatus(ownedAssertions);
            const resources = [
              ...new Set(
                ownedAssertions.map((assertion) => assertion.resource_type),
              ),
            ];
            const operations = [
              ...new Set(
                ownedAssertions.map((assertion) => assertion.operation),
              ),
            ];
            const lastVerifiedAt = ownedAssertions.reduce<string | null>(
              (latest, assertion) =>
                latest === null || assertion.last_verified_at > latest
                  ? assertion.last_verified_at
                  : latest,
              null,
            );
            const selected = visibleSelectedIds.includes(
              implementation.implementationId,
            );
            const hasPlatformPeer =
              (platformCounts.get(implementation.platform) ?? 0) > 1;
            const comparisonDisabled =
              !hasPlatformPeer ||
              (!selected && visibleSelectedIds.length >= 3) ||
              (!selected &&
                Boolean(selectedPlatform) &&
                selectedPlatform !== implementation.platform);

            return (
              <article
                className="grid min-w-0 gap-4 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4"
                data-implementation-id={implementation.implementationId}
                key={implementation.implementationId}
              >
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase text-[#B47767]">
                      {capabilityPlatformLabel(implementation.platform)}
                    </p>
                    <h2 className="mt-1 break-all text-lg font-semibold text-[#2E201C]">
                      {implementation.implementationId}
                    </h2>
                    <p className="mt-1 break-all text-xs text-[#7A625A]">
                      provider · {implementation.providerId}
                    </p>
                  </div>
                  <WorkbenchTag
                    tone={status === "verified" ? "green" : status === "candidate" ? "amber" : "muted"}
                  >
                    {capabilityStatusLabel(status)}
                  </WorkbenchTag>
                </div>

                {status === "candidate" ? (
                  <p className="text-xs font-semibold text-[#B85F4F]">
                    Candidate 仅供审查，尚不可执行。
                  </p>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  <WorkbenchTag tone="neutral">{evidenceLevel}</WorkbenchTag>
                  <WorkbenchTag tone="muted">
                    {implementation.accessChannel}
                  </WorkbenchTag>
                  <WorkbenchTag tone="muted">
                    {implementation.deploymentMode}
                  </WorkbenchTag>
                </div>

                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  <Fact label="resources" value={resources.join(", ") || "none"} />
                  <Fact label="operations" value={operations.join(", ") || "none"} />
                  <Fact
                    label="last verified"
                    value={lastVerifiedAt ?? "not verified"}
                  />
                  <Fact
                    label="evidence refs"
                    value={String(
                      new Set(
                        ownedAssertions.flatMap(
                          (assertion) => assertion.evidence_refs,
                        ),
                      ).size,
                    )}
                  />
                </dl>

                <div className="flex flex-col gap-2 border-t border-[#F0E1D9] pt-3 sm:flex-row sm:items-center sm:justify-between">
                  <label className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-[#7A625A]">
                    <input
                      aria-label={`选择比较 ${implementation.implementationId}`}
                      checked={selected}
                      className="h-4 w-4 accent-[#C96F5C]"
                      disabled={comparisonDisabled}
                      onChange={() => toggleComparison(implementation)}
                      type="checkbox"
                    />
                    加入比较
                  </label>
                  <button
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7D4F43] outline-none transition hover:border-[#C96F5C] hover:bg-[#FFF1EC] focus-visible:ring-4 focus-visible:ring-[#F3D7CE]"
                    onClick={(event) =>
                      onSelectImplementation(
                        implementation.implementationId,
                        event.currentTarget,
                      )
                    }
                    type="button"
                  >
                    能力详情
                    <ArrowUpRight size={15} aria-hidden="true" />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-[#D9C4BA] bg-[#FFFDFC] p-8 text-center text-sm font-semibold text-[#7A625A]">
          当前筛选条件下没有实现；未使用静态实现回退。
        </p>
      )}
    </WorkbenchPanel>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-[#F0E1D9] bg-white p-3">
      <dt className="text-xs font-semibold uppercase text-[#B47767]">{label}</dt>
      <dd className="mt-1 break-words text-sm font-semibold text-[#3B2924]">
        {value}
      </dd>
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
