"use client";

import type { Route } from "next";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { WorkflowPlanPreview } from "@/components/workflow-planner/workflow-plan-preview";
import { WorkflowPlanVersionCompare } from "@/components/workflow-planner/workflow-plan-version-compare";
import { WorkflowPlanVersionHistory } from "@/components/workflow-planner/workflow-plan-version-history";
import { ApiRequestError } from "@/lib/api/client";
import {
  cloneWorkflowPlan,
  copyMonitoringScopeTemplate,
  getWorkflowPlan,
  listMonitoringScopes,
  listWorkflowPlanVersions,
} from "@/lib/api/workflow-plan-persistence";
import type { ProjectStatus } from "@/types/project";
import type {
  MonitoringScope,
  MonitoringScopeListResult,
  MonitoringScopeTemplateCopyResult,
  WorkflowPlanCloneResult,
  WorkflowPlanDetail,
  WorkflowPlanReadBoundary,
  WorkflowVersionListResult,
  WorkflowVersionSummary,
} from "@/types/workflow-plan-persistence";

const HISTORY_PAGE_LIMIT = 50;
const SCOPE_PAGE_LIMIT = 100;

type ReadyAssetState = {
  status: "ready";
  detail: WorkflowPlanDetail;
  scopes: MonitoringScope[];
  versions: WorkflowVersionSummary[];
  total: number;
  nextOffset: number;
  loadingMore: boolean;
  loadMoreError: string | null;
};

type AssetState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | ReadyAssetState;

type CloneState =
  | { status: "idle" }
  | { status: "submitting" }
  | {
      status: "success";
      result: WorkflowPlanCloneResult;
    }
  | { status: "error"; message: string };

type ScopeCopyState =
  | { status: "idle" }
  | { status: "submitting"; scopeId: string }
  | {
      status: "success";
      scopeId: string;
      result: MonitoringScopeTemplateCopyResult;
    }
  | { status: "error"; scopeId: string; message: string };

type MutationAttempt = {
  fingerprint: string;
  idempotencyKey: string;
};

function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

function detailErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError && error.status === 404) {
    return "资源不存在或无权访问";
  }
  return error instanceof Error && error.message.trim()
    ? error.message
    : "WorkflowPlan 详情暂不可用";
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
    throw new Error("WorkflowPlan read boundary mismatch");
  }
}

function assertVersionSummaryContext(
  version: WorkflowVersionSummary,
  workspaceId: string,
  projectId: string,
  planId: string,
): void {
  if (
    version.workspaceId !== workspaceId ||
    version.projectId !== projectId ||
    version.workflowPlanId !== planId ||
    !Number.isSafeInteger(version.versionNumber) ||
    version.versionNumber < 1
  ) {
    throw new Error("WorkflowVersion history context mismatch");
  }
}

function assertStrictDescending(versions: WorkflowVersionSummary[]): void {
  const ids = new Set<string>();
  const numbers = new Set<number>();
  for (let index = 0; index < versions.length; index += 1) {
    const version = versions[index]!;
    if (ids.has(version.id) || numbers.has(version.versionNumber)) {
      throw new Error("WorkflowVersion history identity mismatch");
    }
    ids.add(version.id);
    numbers.add(version.versionNumber);
    const previous = versions[index - 1];
    if (previous && previous.versionNumber <= version.versionNumber) {
      throw new Error("WorkflowVersion history order mismatch");
    }
  }
}

function assertVersionPage(
  result: WorkflowVersionListResult,
  context: {
    projectId: string;
    planId: string;
    workspaceId: string;
    projectStatus: ProjectStatus;
    expectedOffset: number;
  },
): void {
  assertFalseBoundary(result);
  if (
    result.projectStatus !== context.projectStatus ||
    result.limit !== HISTORY_PAGE_LIMIT ||
    result.offset !== context.expectedOffset ||
    !Number.isSafeInteger(result.total) ||
    result.total < result.offset + result.items.length ||
    result.items.length > HISTORY_PAGE_LIMIT ||
    (result.items.length === 0 && result.offset < result.total)
  ) {
    throw new Error("WorkflowVersion history response context mismatch");
  }
  for (const version of result.items) {
    assertVersionSummaryContext(
      version,
      context.workspaceId,
      context.projectId,
      context.planId,
    );
  }
  assertStrictDescending(result.items);
}

function assertScopeList(
  result: MonitoringScopeListResult,
  projectId: string,
  projectStatus: ProjectStatus,
): void {
  assertFalseBoundary(result);
  if (
    result.projectStatus !== projectStatus ||
    !Number.isSafeInteger(result.total) ||
    result.total < result.offset + result.items.length ||
    result.items.length > result.limit ||
    result.items.some((scope) => scope.projectId !== projectId)
  ) {
    throw new Error("MonitoringScope list response context mismatch");
  }
}

async function listAllMonitoringScopes(
  projectId: string,
  projectStatus: ProjectStatus,
  signal: AbortSignal,
): Promise<MonitoringScope[]> {
  const items: MonitoringScope[] = [];
  const ids = new Set<string>();
  let offset = 0;
  let total: number | null = null;

  while (total === null || offset < total) {
    const page = await listMonitoringScopes(projectId, {
      limit: SCOPE_PAGE_LIMIT,
      offset,
      signal,
    });
    assertScopeList(page, projectId, projectStatus);
    if (
      page.limit !== SCOPE_PAGE_LIMIT ||
      page.offset !== offset ||
      (total !== null && page.total !== total) ||
      (page.items.length === 0 && page.offset < page.total)
    ) {
      throw new Error("MonitoringScope list pagination mismatch");
    }
    for (const scope of page.items) {
      if (ids.has(scope.id)) {
        throw new Error("MonitoringScope list identity mismatch");
      }
      ids.add(scope.id);
      items.push(scope);
    }
    total = page.total;
    offset += page.items.length;
  }
  return items;
}

function assertInitialResponses(
  detail: WorkflowPlanDetail,
  history: WorkflowVersionListResult,
  projectId: string,
  planId: string,
): void {
  assertFalseBoundary(detail);
  const plan = detail.plan;
  const current = detail.currentVersion;
  if (
    plan.id !== planId ||
    plan.projectId !== projectId ||
    current.workspaceId !== plan.workspaceId ||
    current.projectId !== projectId ||
    current.workflowPlanId !== planId ||
    current.id !== plan.currentVersionId ||
    current.versionNumber !== plan.currentVersionNumber ||
    current.editableInput.flowMode !== plan.flowMode
  ) {
    throw new Error("WorkflowPlan detail response context mismatch");
  }
  assertVersionPage(history, {
    projectId,
    planId,
    workspaceId: plan.workspaceId,
    projectStatus: detail.projectStatus,
    expectedOffset: 0,
  });
  const first = history.items[0];
  if (
    !first ||
    first.id !== plan.currentVersionId ||
    first.versionNumber !== plan.currentVersionNumber
  ) {
    throw new Error("WorkflowPlan current Version history mismatch");
  }
}

function duplicateVersionMatches(
  left: WorkflowVersionSummary,
  right: WorkflowVersionSummary,
): boolean {
  return (
    left.id === right.id &&
    left.projectId === right.projectId &&
    left.workflowPlanId === right.workflowPlanId &&
    left.versionNumber === right.versionNumber &&
    left.previewFingerprint === right.previewFingerprint &&
    left.createdAt === right.createdAt
  );
}

function mergeVersionPages(
  existing: WorkflowVersionSummary[],
  incoming: WorkflowVersionSummary[],
): WorkflowVersionSummary[] {
  const merged = [...existing];
  const byId = new Map(existing.map((version) => [version.id, version]));
  const idByNumber = new Map(
    existing.map((version) => [version.versionNumber, version.id]),
  );

  for (const version of incoming) {
    const duplicate = byId.get(version.id);
    if (duplicate) {
      if (!duplicateVersionMatches(duplicate, version)) {
        throw new Error("WorkflowVersion duplicate identity mismatch");
      }
      continue;
    }
    const numberOwner = idByNumber.get(version.versionNumber);
    if (numberOwner && numberOwner !== version.id) {
      throw new Error("WorkflowVersion number identity mismatch");
    }
    byId.set(version.id, version);
    idByNumber.set(version.versionNumber, version.id);
    merged.push(version);
  }
  assertStrictDescending(merged);
  return merged;
}

function currentPlannerHref(detail: WorkflowPlanDetail): Route {
  const query = new URLSearchParams();
  query.set("mode", detail.plan.flowMode);
  query.set("project_id", detail.plan.projectId);
  query.set("plan_id", detail.plan.id);
  return `/automation/planner?${query.toString()}` as Route;
}

function planDetailHref(projectId: string, planId: string): Route {
  return `/automation/projects/${encodeURIComponent(projectId)}/plans/${encodeURIComponent(planId)}` as Route;
}

export function WorkflowPlanDetailWorkspace({
  projectId,
  planId,
}: {
  projectId: string;
  planId: string;
}) {
  return (
    <WorkflowPlanDetailAsset
      key={JSON.stringify([projectId, planId])}
      planId={planId}
      projectId={projectId}
    />
  );
}

function WorkflowPlanDetailAsset({
  projectId,
  planId,
}: {
  projectId: string;
  planId: string;
}) {
  const [assetState, setAssetState] = useState<AssetState>({
    status: "loading",
  });
  const [cloneName, setCloneName] = useState("");
  const [cloneState, setCloneState] = useState<CloneState>({ status: "idle" });
  const [scopeCopyState, setScopeCopyState] = useState<ScopeCopyState>({
    status: "idle",
  });
  const [retrySequence, setRetrySequence] = useState(0);
  const detailSequenceRef = useRef(0);
  const historySequenceRef = useRef(0);
  const historyControllerRef = useRef<AbortController | null>(null);
  const cloneAttemptRef = useRef<MutationAttempt | null>(null);
  const scopeCopyAttemptRefs = useRef(new Map<string, MutationAttempt>());
  const contextRef = useRef({ projectId, planId });
  contextRef.current = { projectId, planId };

  useEffect(() => {
    const sequence = detailSequenceRef.current + 1;
    detailSequenceRef.current = sequence;
    historyControllerRef.current?.abort();
    historySequenceRef.current += 1;
    const controller = new AbortController();
    const options = { signal: controller.signal };
    setAssetState({ status: "loading" });

    const detailRequest = getWorkflowPlan(projectId, planId, options);
    const historyRequest = listWorkflowPlanVersions(projectId, planId, {
      limit: HISTORY_PAGE_LIMIT,
      offset: 0,
      signal: controller.signal,
    });
    const scopesRequest = detailRequest.then((detail) =>
      listAllMonitoringScopes(
        projectId,
        detail.projectStatus,
        controller.signal,
      ),
    );

    void Promise.all([detailRequest, historyRequest, scopesRequest])
      .then(([detail, history, scopes]) => {
        const context = contextRef.current;
        if (
          controller.signal.aborted ||
          detailSequenceRef.current !== sequence ||
          context.projectId !== projectId ||
          context.planId !== planId
        ) {
          return;
        }
        assertInitialResponses(detail, history, projectId, planId);
        setAssetState({
          status: "ready",
          detail,
          scopes,
          versions: history.items,
          total: history.total,
          nextOffset: history.offset + history.items.length,
          loadingMore: false,
          loadMoreError: null,
        });
        setCloneName(`${detail.plan.name} copy`);
        setCloneState({ status: "idle" });
        setScopeCopyState({ status: "idle" });
      })
      .catch((error: unknown) => {
        const context = contextRef.current;
        if (
          controller.signal.aborted ||
          detailSequenceRef.current !== sequence ||
          context.projectId !== projectId ||
          context.planId !== planId ||
          isAbortError(error)
        ) {
          return;
        }
        setAssetState({
          status: "error",
          message: detailErrorMessage(error),
        });
      });

    return () => {
      controller.abort();
      detailSequenceRef.current += 1;
      historyControllerRef.current?.abort();
      historySequenceRef.current += 1;
    };
  }, [planId, projectId, retrySequence]);

  function loadMoreHistory(): void {
    if (
      assetState.status !== "ready" ||
      assetState.loadingMore ||
      assetState.nextOffset >= assetState.total
    ) {
      return;
    }
    const snapshot = assetState;
    const requestedOffset = snapshot.nextOffset;
    const sequence = historySequenceRef.current + 1;
    historySequenceRef.current = sequence;
    historyControllerRef.current?.abort();
    const controller = new AbortController();
    historyControllerRef.current = controller;
    setAssetState({
      ...snapshot,
      loadingMore: true,
      loadMoreError: null,
    });

    void listWorkflowPlanVersions(projectId, planId, {
      limit: HISTORY_PAGE_LIMIT,
      offset: requestedOffset,
      signal: controller.signal,
    })
      .then((page) => {
        const context = contextRef.current;
        if (
          controller.signal.aborted ||
          historySequenceRef.current !== sequence ||
          context.projectId !== projectId ||
          context.planId !== planId
        ) {
          return;
        }
        assertVersionPage(page, {
          projectId,
          planId,
          workspaceId: snapshot.detail.plan.workspaceId,
          projectStatus: snapshot.detail.projectStatus,
          expectedOffset: requestedOffset,
        });
        if (page.total !== snapshot.total) {
          throw new Error(
            "WorkflowVersion history total changed during paging",
          );
        }
        const merged = mergeVersionPages(snapshot.versions, page.items);
        setAssetState((current) => {
          if (
            current.status !== "ready" ||
            historySequenceRef.current !== sequence
          ) {
            return current;
          }
          return {
            ...current,
            versions: merged,
            total: page.total,
            nextOffset: page.offset + page.items.length,
            loadingMore: false,
            loadMoreError: null,
          };
        });
      })
      .catch((error: unknown) => {
        const context = contextRef.current;
        if (
          controller.signal.aborted ||
          historySequenceRef.current !== sequence ||
          context.projectId !== projectId ||
          context.planId !== planId ||
          isAbortError(error)
        ) {
          return;
        }
        setAssetState((current) =>
          current.status === "ready"
            ? {
                ...current,
                loadingMore: false,
                loadMoreError: detailErrorMessage(error),
              }
            : current,
        );
      });
  }

  async function cloneCurrentPlan(): Promise<void> {
    if (
      assetState.status !== "ready" ||
      detail.projectStatus === "archived" ||
      cloneName.trim().length < 1 ||
      cloneName.trim().length > 200
    ) {
      return;
    }
    setCloneState({ status: "submitting" });
    const fingerprint = JSON.stringify([
      projectId,
      planId,
      assetState.detail.plan.currentVersionId,
      cloneName,
    ]);
    const previousAttempt = cloneAttemptRef.current;
    const attempt =
      previousAttempt?.fingerprint === fingerprint
        ? previousAttempt
        : { fingerprint, idempotencyKey: crypto.randomUUID() };
    cloneAttemptRef.current = attempt;
    try {
      const result = await cloneWorkflowPlan(projectId, planId, {
        name: cloneName,
        sourceVersionId: assetState.detail.plan.currentVersionId,
        idempotencyKey: attempt.idempotencyKey,
      });
      const mutationBoundaryMatches = result.idempotentReplay
        ? result.databaseWrite === false && result.planChanged === false
        : result.databaseWrite === true && result.planChanged === true;
      if (
        !mutationBoundaryMatches ||
        result.providerCall !== false ||
        result.actorRun !== false ||
        result.browserRun !== false ||
        result.llmCall !== false ||
        result.workflowRunCreated !== false ||
        result.executionAuthorized !== false
      ) {
        throw new Error("WorkflowPlan clone boundary mismatch");
      }
      cloneAttemptRef.current = null;
      setCloneState({ status: "success", result });
    } catch (error: unknown) {
      setCloneState({ status: "error", message: detailErrorMessage(error) });
    }
  }

  async function copyScope(scope: MonitoringScope): Promise<void> {
    if (assetState.status !== "ready" || archived) {
      return;
    }
    setScopeCopyState({ status: "submitting", scopeId: scope.id });
    const fingerprint = JSON.stringify([
      projectId,
      scope.id,
      assetState.detail.plan.currentVersionId,
    ]);
    const previousAttempt = scopeCopyAttemptRefs.current.get(scope.id);
    const attempt =
      previousAttempt?.fingerprint === fingerprint
        ? previousAttempt
        : { fingerprint, idempotencyKey: crypto.randomUUID() };
    scopeCopyAttemptRefs.current.set(scope.id, attempt);
    try {
      const result = await copyMonitoringScopeTemplate(projectId, scope.id, {
        sourceVersionId: assetState.detail.plan.currentVersionId,
        idempotencyKey: attempt.idempotencyKey,
      });
      const mutationBoundaryMatches = result.idempotentReplay
        ? result.databaseWrite === false
        : result.databaseWrite === true;
      if (
        !mutationBoundaryMatches ||
        result.providerCall !== false ||
        result.actorRun !== false ||
        result.browserRun !== false ||
        result.llmCall !== false ||
        result.workflowRunCreated !== false ||
        result.executionAuthorized !== false
      ) {
        throw new Error("MonitoringScope template boundary mismatch");
      }
      scopeCopyAttemptRefs.current.delete(scope.id);
      setScopeCopyState({ status: "success", scopeId: scope.id, result });
    } catch (error: unknown) {
      setScopeCopyState({
        status: "error",
        scopeId: scope.id,
        message: detailErrorMessage(error),
      });
    }
  }

  if (assetState.status === "loading") {
    return <DetailStatus message="正在加载 WorkflowPlan 详情…" />;
  }
  if (assetState.status === "error") {
    return (
      <section className="rounded-2xl border border-[#E4B9A7] bg-[#FFF5EF] p-4">
        <p className="text-sm font-semibold text-[#803F32]" role="alert">
          {assetState.message}
        </p>
        <button
          className="mt-3 rounded-xl border border-[#C97865] bg-white px-4 py-2 text-sm font-semibold text-[#8A4436]"
          onClick={() => setRetrySequence((current) => current + 1)}
          type="button"
        >
          重新加载
        </button>
      </section>
    );
  }

  const { detail, versions } = assetState;
  const archived = detail.projectStatus === "archived";
  const versionScopeKeys = new Set(
    (detail.currentVersion.preview.normalizedInput?.scopes ?? []).map(
      (scope) => scope.scopeKey,
    ),
  );
  const versionScopes = assetState.scopes.filter((scope) =>
    versionScopeKeys.has(scope.scopeKey),
  );

  return (
    <div
      className="grid min-w-0 gap-5"
      data-testid="workflow-plan-detail-workspace"
    >
      <section className="min-w-0 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 sm:p-5">
        <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9A7467]">
              WorkflowPlan Asset
            </p>
            <h1 className="mt-1 break-words text-2xl font-semibold text-[#2E201C]">
              {detail.plan.name}
            </h1>
            <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
              <span className="rounded-full bg-[#FBF1EC] px-3 py-1 text-[#8A4436]">
                {detail.plan.planningStatus}
              </span>
              <span className="rounded-full bg-white px-3 py-1 text-[#6D514A]">
                当前 v{detail.plan.currentVersionNumber}
              </span>
              <span className="rounded-full bg-white px-3 py-1 font-mono text-[#6D514A]">
                Project ID: {detail.plan.projectId}
              </span>
              {archived ? (
                <span className="rounded-full bg-[#FFF4DE] px-3 py-1 text-[#8A5B00]">
                  Archived Project · 只读
                </span>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Link
              className="inline-flex min-h-10 items-center rounded-xl border border-[#DCCFC8] bg-white px-4 py-2 text-sm font-semibold text-[#6D514A]"
              href={"/automation/plans" as Route}
            >
              返回已保存计划
            </Link>
            <Link
              className="inline-flex min-h-10 items-center rounded-xl border border-[#C97865] bg-white px-4 py-2 text-sm font-semibold text-[#8A4436]"
              href={currentPlannerHref(detail)}
            >
              {archived ? "在 Planner 中查看（只读）" : "Edit in Planner"}
            </Link>
          </div>
        </div>
      </section>

      {!archived && versionScopes.length > 0 ? (
        <section
          aria-labelledby="workflow-scope-template-copy-heading"
          className="min-w-0 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 sm:p-5"
          data-testid="workflow-scope-template-copy-panel"
        >
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9A7467]">
              Scope template
            </p>
            <h2
              className="mt-1 text-lg font-semibold text-[#2E201C]"
              id="workflow-scope-template-copy-heading"
            >
              复制当前 Version 的 Scope 模板
            </h2>
            <p className="mt-2 text-sm leading-6 text-[#716562]">
              生成独立草稿模板，不增加 canonical Scope，也不会启动运行。
            </p>
          </div>
          <ul className="mt-4 grid gap-3">
            {versionScopes.map((scope) => {
              const busy =
                scopeCopyState.status === "submitting" &&
                scopeCopyState.scopeId === scope.id;
              const copied =
                scopeCopyState.status === "success" &&
                scopeCopyState.scopeId === scope.id;
              const failed =
                scopeCopyState.status === "error" &&
                scopeCopyState.scopeId === scope.id;
              return (
                <li
                  className="flex min-w-0 flex-col gap-3 rounded-xl border border-[#E9E1DC] bg-white p-4 sm:flex-row sm:items-center sm:justify-between"
                  key={scope.id}
                >
                  <div className="min-w-0">
                    <p className="font-semibold text-[#392823]">
                      {scope.scopeKey}
                    </p>
                    <p className="mt-1 break-all text-xs text-[#716562]">
                      {scope.canonicalTerm ?? scope.scopeType}
                    </p>
                    {copied ? (
                      <p className="mt-2 text-xs font-semibold text-[#356152]" role="status">
                        已复制模板：{scopeCopyState.result.template.id}
                      </p>
                    ) : null}
                    {failed ? (
                      <p className="mt-2 text-xs font-semibold text-[#B85F4F]" role="alert">
                        {scopeCopyState.message}
                      </p>
                    ) : null}
                  </div>
                  <button
                    aria-busy={busy}
                    className="inline-flex min-h-10 shrink-0 items-center justify-center rounded-xl border border-[#C97865] bg-white px-4 py-2 text-sm font-semibold text-[#8A4436] disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={archived || busy}
                    onClick={() => void copyScope(scope)}
                    type="button"
                  >
                    {busy ? "正在复制…" : "复制 Scope 模板"}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {!archived ? (
        <section
          aria-labelledby="workflow-plan-clone-heading"
          className="min-w-0 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 sm:p-5"
          data-testid="workflow-plan-clone-panel"
        >
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9A7467]">
            Independent copy
          </p>
          <h2
            className="mt-1 text-lg font-semibold text-[#2E201C]"
            id="workflow-plan-clone-heading"
          >
            复制为新 WorkflowPlan
          </h2>
          <p className="mt-2 text-sm leading-6 text-[#716562]">
            复制当前冻结 Version，生成新的 Plan/v1；不会激活、运行或调用 Provider。
          </p>
        </div>
        <div className="mt-4 flex min-w-0 flex-col gap-3 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1 text-sm font-semibold text-[#463530]">
            新 Plan 名称
            <input
              className="mt-2 w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm font-normal outline-none focus:border-[#C97865]"
              maxLength={200}
              onChange={(event) => setCloneName(event.target.value)}
              value={cloneName}
            />
          </label>
          <button
            aria-busy={cloneState.status === "submitting"}
            className="inline-flex min-h-10 items-center justify-center rounded-xl bg-[#9F4E3D] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#CDBEB9]"
            data-testid="workflow-plan-clone"
            disabled={
              archived ||
              cloneState.status === "submitting" ||
              cloneName.trim().length < 1 ||
              cloneName.trim().length > 200
            }
            onClick={() => void cloneCurrentPlan()}
            type="button"
          >
            {cloneState.status === "submitting" ? "正在复制…" : "复制为新计划"}
          </button>
        </div>
        {cloneState.status === "success" ? (
          <p className="mt-4 text-sm font-semibold text-[#356152]" role="status">
            已创建独立 Plan/v1：{" "}
            <Link
              className="underline decoration-[#8BBE9E] underline-offset-4"
              href={planDetailHref(projectId, cloneState.result.plan.id)}
            >
              {cloneState.result.plan.name}
            </Link>
            。来源 v{detail.plan.currentVersionNumber} 已保留。
          </p>
        ) : null}
        {cloneState.status === "error" ? (
          <p className="mt-4 text-sm font-semibold text-[#B85F4F]" role="alert">
            {cloneState.message}
          </p>
        ) : null}
        </section>
      ) : null}

      <section
        aria-labelledby="current-workflow-plan-preview-heading"
        className="min-w-0 rounded-2xl border border-[#E8DDD6] bg-white p-4 sm:p-5"
      >
        <h2
          className="mb-4 text-lg font-semibold text-[#2E201C]"
          id="current-workflow-plan-preview-heading"
        >
          当前 Version Preview
        </h2>
        <WorkflowPlanPreview
          preview={detail.currentVersion.preview}
          stale={false}
        />
      </section>

      <WorkflowPlanVersionHistory
        hasMore={assetState.nextOffset < assetState.total}
        loadMoreError={assetState.loadMoreError}
        loadingMore={assetState.loadingMore}
        onLoadMore={loadMoreHistory}
        plan={detail.plan}
        projectStatus={detail.projectStatus}
        total={assetState.total}
        versions={versions}
      />

      <WorkflowPlanVersionCompare
        plan={detail.plan}
        planId={planId}
        projectId={projectId}
        projectStatus={detail.projectStatus}
        versions={versions}
      />
    </div>
  );
}

function DetailStatus({ message }: { message: string }) {
  return (
    <p
      className="rounded-2xl border border-[#E8DDD6] bg-white px-4 py-6 text-sm text-[#716562]"
      role="status"
    >
      {message}
    </p>
  );
}
