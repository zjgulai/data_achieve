import { ArrowUpRight, Layers3 } from "lucide-react";

import {
  WorkbenchPanel,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import {
  capabilityPlatformLabel,
  capabilityStatusLabel,
  groupCapabilityScenarios,
} from "@/lib/capability-market";
import type {
  CapabilityAssertion,
  CapabilityImplementation,
} from "@/types/capability";

type CapabilityScenarioViewProps = {
  assertions: CapabilityAssertion[];
  implementations: CapabilityImplementation[];
  evidenceLevel: string;
  onSelectImplementation: (
    implementationId: string,
    trigger: HTMLElement,
  ) => void;
};

export function CapabilityScenarioView({
  assertions,
  evidenceLevel,
  implementations,
  onSelectImplementation,
}: CapabilityScenarioViewProps) {
  const scenarios = groupCapabilityScenarios(assertions);
  const implementationById = new Map(
    implementations.map((implementation) => [
      implementation.implementationId,
      implementation,
    ]),
  );

  return (
    <WorkbenchPanel
      icon={Layers3}
      label="Scenario index"
      subtitle="固定八类业务需求；空场景保留位置，避免把缺失事实误报为不支持。"
      title="按业务场景定位能力"
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {scenarios.map((scenario, index) => {
          const implementationIds = [
            ...new Set(
              scenario.assertions.map(
                (assertion) => assertion.implementation_id,
              ),
            ),
          ].filter((implementationId) =>
            implementationById.has(implementationId),
          );
          const scenarioImplementations = implementationIds.flatMap(
            (implementationId) => {
              const implementation = implementationById.get(implementationId);
              return implementation ? [implementation] : [];
            },
          );
          const platformLabels = [
            ...new Set(
              scenarioImplementations.map((implementation) =>
                capabilityPlatformLabel(implementation.platform),
              ),
            ),
          ];
          const evidenceCount = new Set(
            scenario.assertions.flatMap((assertion) => assertion.evidence_refs),
          ).size;
          const statuses = [
            ...new Set(
              scenario.assertions.map((assertion) => assertion.support_status),
            ),
          ];
          const firstImplementationId = implementationIds[0] ?? null;
          const hasCandidate = statuses.includes("candidate");

          return (
            <article
              className="group grid min-h-64 content-between gap-5 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4 transition-colors hover:border-[#D9A99C]"
              data-testid="capability-scenario"
              key={scenario.id}
            >
              <div className="grid gap-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#B47767]">
                      Scenario {String(index + 1).padStart(2, "0")}
                    </p>
                    <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">
                      {scenario.label}
                    </h2>
                  </div>
                  <WorkbenchTag tone={scenario.assertions.length ? "amber" : "muted"}>
                    {scenario.assertions.length} assertions
                  </WorkbenchTag>
                </div>

                <dl className="grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-xl border border-[#F0E1D9] bg-white p-3">
                    <dt className="text-xs font-semibold uppercase text-[#B47767]">
                      platforms
                    </dt>
                    <dd className="mt-1 font-semibold text-[#2E201C]">
                      {platformLabels.length}
                    </dd>
                  </div>
                  <div className="rounded-xl border border-[#F0E1D9] bg-white p-3">
                    <dt className="text-xs font-semibold uppercase text-[#B47767]">
                      evidence refs
                    </dt>
                    <dd className="mt-1 font-semibold text-[#2E201C]">
                      {evidenceCount}
                    </dd>
                  </div>
                </dl>

                <div className="flex min-h-14 flex-wrap content-start gap-2">
                  <WorkbenchTag tone="neutral">{evidenceLevel}</WorkbenchTag>
                  {statuses.map((status) => (
                    <WorkbenchTag
                      key={status}
                      tone={status === "verified" ? "green" : status === "candidate" ? "amber" : "muted"}
                    >
                      {capabilityStatusLabel(status)}
                    </WorkbenchTag>
                  ))}
                </div>

                <p className="line-clamp-2 min-h-10 text-xs leading-5 text-[#7A625A]">
                  {platformLabels.length > 0
                    ? platformLabels.join(" · ")
                    : "当前筛选范围没有可审查的规范能力事实。"}
                </p>
                {hasCandidate ? (
                  <p className="text-xs font-semibold text-[#B85F4F]">
                    Candidate 仅供审查，尚不可执行。
                  </p>
                ) : null}
              </div>

              <button
                className="inline-flex min-h-11 w-full items-center justify-between rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7D4F43] outline-none transition hover:border-[#C96F5C] hover:bg-[#FFF1EC] focus-visible:ring-4 focus-visible:ring-[#F3D7CE] disabled:cursor-not-allowed disabled:bg-[#FBF8F5] disabled:text-[#B7A49C]"
                disabled={!firstImplementationId}
                onClick={(event) => {
                  if (firstImplementationId) {
                    onSelectImplementation(
                      firstImplementationId,
                      event.currentTarget,
                    );
                  }
                }}
                type="button"
              >
                {firstImplementationId ? "审查首个实现" : "暂无可审查实现"}
                <ArrowUpRight size={16} aria-hidden="true" />
              </button>
            </article>
          );
        })}
      </div>
    </WorkbenchPanel>
  );
}
