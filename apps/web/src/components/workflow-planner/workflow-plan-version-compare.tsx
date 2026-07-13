"use client";

import { useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/lib/api/client";
import { compareWorkflowPlanVersions } from "@/lib/api/workflow-plan-persistence";
import type { ProjectStatus } from "@/types/project";
import type {
  WorkflowPlan,
  WorkflowPlanReadBoundary,
  WorkflowPlanVersionCompare,
  WorkflowVersionSummary,
} from "@/types/workflow-plan-persistence";
import type { PlannerJsonValue } from "@/types/workflow-planner";

type CompareState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; result: WorkflowPlanVersionCompare }
  | { status: "error"; message: string };

function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

function compareErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError && error.status === 404) {
    return "资源不存在或无权访问";
  }
  return error instanceof Error && error.message.trim()
    ? error.message
    : "Version Compare 暂不可用";
}

function assertFalseBoundary(value: WorkflowPlanReadBoundary): void {
  if (
    value.databaseWrite !== false ||
    value.planChanged !== false ||
    value.providerCall !== false ||
    value.actorRun !== false ||
    value.browserRun !== false ||
    value.llmCall !== false ||
    value.workflowRunCreated !== false ||
    value.executionAuthorized !== false
  ) {
    throw new Error("WorkflowPlan Compare boundary mismatch");
  }
}

function assertCompareResponse(
  result: WorkflowPlanVersionCompare,
  context: {
    projectId: string;
    planId: string;
    workspaceId: string;
    projectStatus: ProjectStatus;
    currentVersionId: string;
    currentVersionNumber: number;
    baseVersionId: string;
    targetVersionId: string;
  },
): void {
  assertFalseBoundary(result);
  const planMismatch =
    result.projectStatus !== context.projectStatus ||
    result.plan.workspaceId !== context.workspaceId ||
    result.plan.id !== context.planId ||
    result.plan.projectId !== context.projectId ||
    result.plan.currentVersionId !== context.currentVersionId ||
    result.plan.currentVersionNumber !== context.currentVersionNumber;
  const baseMismatch =
    result.baseVersion.id !== context.baseVersionId ||
    result.baseVersion.workspaceId !== context.workspaceId ||
    result.baseVersion.projectId !== context.projectId ||
    result.baseVersion.workflowPlanId !== context.planId;
  const targetMismatch =
    result.targetVersion.id !== context.targetVersionId ||
    result.targetVersion.workspaceId !== context.workspaceId ||
    result.targetVersion.projectId !== context.projectId ||
    result.targetVersion.workflowPlanId !== context.planId;
  const sameVersionMismatch =
    result.sameVersion !== (context.baseVersionId === context.targetVersionId);
  const sameVersionSectionsMismatch =
    result.sameVersion && result.sections.length !== 0;

  if (
    planMismatch ||
    baseMismatch ||
    targetMismatch ||
    sameVersionMismatch ||
    sameVersionSectionsMismatch
  ) {
    throw new Error("WorkflowPlan Compare response context mismatch");
  }
}

export function WorkflowPlanVersionCompare({
  projectId,
  planId,
  projectStatus,
  plan,
  versions,
}: {
  projectId: string;
  planId: string;
  projectStatus: ProjectStatus;
  plan: WorkflowPlan;
  versions: WorkflowVersionSummary[];
}) {
  const [baseVersionId, setBaseVersionId] = useState(
    () => versions[1]?.id ?? versions[0]?.id ?? "",
  );
  const [targetVersionId, setTargetVersionId] = useState(
    () => versions[0]?.id ?? "",
  );
  const [compareState, setCompareState] = useState<CompareState>({
    status: "idle",
  });
  const requestSequenceRef = useRef(0);
  const canCompare = versions.length >= 2;
  const workspaceId = plan.workspaceId;
  const currentVersionId = plan.currentVersionId;
  const currentVersionNumber = plan.currentVersionNumber;

  useEffect(() => {
    if (!canCompare || !baseVersionId || !targetVersionId) {
      setCompareState({ status: "idle" });
      return;
    }

    const sequence = requestSequenceRef.current + 1;
    requestSequenceRef.current = sequence;
    const controller = new AbortController();
    setCompareState({ status: "loading" });

    void compareWorkflowPlanVersions(
      projectId,
      planId,
      baseVersionId,
      targetVersionId,
      { signal: controller.signal },
    )
      .then((result) => {
        if (
          controller.signal.aborted ||
          requestSequenceRef.current !== sequence
        ) {
          return;
        }
        assertCompareResponse(result, {
          projectId,
          planId,
          workspaceId,
          projectStatus,
          currentVersionId,
          currentVersionNumber,
          baseVersionId,
          targetVersionId,
        });
        setCompareState({ status: "ready", result });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          requestSequenceRef.current !== sequence ||
          isAbortError(error)
        ) {
          return;
        }
        setCompareState({
          status: "error",
          message: compareErrorMessage(error),
        });
      });

    return () => {
      controller.abort();
      requestSequenceRef.current += 1;
    };
  }, [
    baseVersionId,
    canCompare,
    currentVersionId,
    currentVersionNumber,
    planId,
    projectId,
    projectStatus,
    targetVersionId,
    workspaceId,
  ]);

  return (
    <section
      aria-labelledby="workflow-plan-version-compare-heading"
      className="min-w-0 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 sm:p-5"
      data-testid="workflow-plan-version-compare"
    >
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9A7467]">
          Server Facts
        </p>
        <h2
          className="mt-1 text-lg font-semibold text-[#2E201C]"
          id="workflow-plan-version-compare-heading"
        >
          Compare Versions
        </h2>
        <p className="mt-2 text-sm leading-6 text-[#716562]">
          仅展示服务端返回的结构化 change sections，不在浏览器中重新计算差异。
        </p>
      </div>

      {canCompare ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <VersionSelect
            id="workflow-plan-compare-base"
            label="Base Version"
            onChange={setBaseVersionId}
            value={baseVersionId}
            versions={versions}
          />
          <VersionSelect
            id="workflow-plan-compare-target"
            label="Target Version"
            onChange={setTargetVersionId}
            value={targetVersionId}
            versions={versions}
          />
        </div>
      ) : (
        <p className="mt-4 rounded-xl border border-[#E8DDD6] bg-white px-4 py-4 text-sm text-[#716562]">
          至少需要 2 个 Version 才能比较。
        </p>
      )}

      <div aria-busy={compareState.status === "loading"} className="mt-4">
        {compareState.status === "loading" ? (
          <CompareStatus message="正在读取结构化差异…" />
        ) : compareState.status === "error" ? (
          <CompareStatus message={compareState.message} role="alert" />
        ) : compareState.status === "ready" ? (
          <CompareResult result={compareState.result} />
        ) : null}
      </div>
    </section>
  );
}

function VersionSelect({
  id,
  label,
  value,
  versions,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  versions: WorkflowVersionSummary[];
  onChange: (value: string) => void;
}) {
  return (
    <label
      className="grid gap-2 text-sm font-semibold text-[#5F514C]"
      htmlFor={id}
    >
      {label}
      <select
        aria-label={label}
        className="min-h-11 rounded-xl border border-[#DCCFC8] bg-white px-3 text-[#392823]"
        id={id}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {versions.map((version) => (
          <option key={version.id} value={version.id}>
            v{version.versionNumber} · {version.planningStatus}
          </option>
        ))}
      </select>
    </label>
  );
}

function CompareStatus({
  message,
  role = "status",
}: {
  message: string;
  role?: "alert" | "status";
}) {
  return (
    <p
      className="rounded-xl border border-[#E8DDD6] bg-white px-4 py-4 text-sm text-[#716562]"
      role={role}
    >
      {message}
    </p>
  );
}

function CompareResult({ result }: { result: WorkflowPlanVersionCompare }) {
  if (result.sameVersion) {
    return <CompareStatus message="同一 Version，无差异。" />;
  }
  if (result.sections.length === 0) {
    return <CompareStatus message="服务端未返回结构化差异。" />;
  }

  return (
    <div className="grid min-w-0 gap-4">
      {result.sections.map((section, sectionIndex) => (
        <section
          className="min-w-0 rounded-xl border border-[#E9E1DC] bg-white p-4"
          key={`${section.key}-${sectionIndex}`}
        >
          <h3 className="break-words font-semibold text-[#392823]">
            {section.key}
          </h3>
          <div className="mt-3 grid min-w-0 gap-3">
            {section.changes.map((change, changeIndex) => (
              <article
                className="min-w-0 rounded-xl bg-[#FBF8F5] p-3"
                key={`${change.field}-${changeIndex}`}
              >
                <h4 className="break-words text-sm font-semibold text-[#7D4F43]">
                  {change.field}
                </h4>
                <div className="mt-3 grid min-w-0 gap-3 lg:grid-cols-2">
                  <CompareSide label="Before" value={change.before} />
                  <CompareSide label="After" value={change.after} />
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function CompareSide({
  label,
  value,
}: {
  label: string;
  value: PlannerJsonValue | null;
}) {
  return (
    <section className="min-w-0 rounded-lg border border-[#E9E1DC] bg-white p-3">
      <h5 className="text-xs font-semibold uppercase tracking-[0.12em] text-[#9A7467]">
        {label}
      </h5>
      <div className="mt-2 min-w-0 text-sm text-[#4D3B36]">
        <CompareValue value={value} />
      </div>
    </section>
  );
}

function CompareValue({ value }: { value: PlannerJsonValue | null }) {
  if (value === null) {
    return <span className="text-[#8B7770]">null</span>;
  }
  if (typeof value === "boolean") {
    return <span>{value ? "true" : "false"}</span>;
  }
  if (typeof value === "number" || typeof value === "string") {
    return <span className="break-words">{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? (
      <span className="text-[#8B7770]">空列表</span>
    ) : (
      <ul className="grid min-w-0 gap-2">
        {value.map((item, index) => (
          <li
            className="min-w-0 rounded-md border border-[#EFE7E2] bg-[#FFFDFC] px-2 py-1.5"
            key={index}
          >
            <CompareValue value={item} />
          </li>
        ))}
      </ul>
    );
  }

  const entries = Object.entries(value);
  return entries.length === 0 ? (
    <span className="text-[#8B7770]">空对象</span>
  ) : (
    <dl className="grid min-w-0 gap-2">
      {entries.map(([key, item]) => (
        <div
          className="min-w-0 rounded-md border border-[#EFE7E2] bg-[#FFFDFC] px-2 py-1.5"
          key={key}
        >
          <dt className="break-words text-xs font-semibold text-[#9A7467]">
            {key}
          </dt>
          <dd className="mt-1 min-w-0">
            <CompareValue value={item} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
