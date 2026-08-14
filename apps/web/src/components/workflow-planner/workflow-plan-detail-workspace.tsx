"use client";

import type { Route } from "next";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { WorkflowPlanPreview } from "@/components/workflow-planner/workflow-plan-preview";
import { WorkflowPlanVersionCompare } from "@/components/workflow-planner/workflow-plan-version-compare";
import { WorkflowPlanVersionHistory } from "@/components/workflow-planner/workflow-plan-version-history";
import { ApiRequestError } from "@/lib/api/client";
import {
  getWorkflowPlan,
  listWorkflowPlanVersions,
} from "@/lib/api/workflow-plan-persistence";
import type { ProjectStatus } from "@/types/project";
import type {
  WorkflowPlanDetail,
  WorkflowPlanReadBoundary,
  WorkflowVersionListResult,
  WorkflowVersionSummary,
} from "@/types/workflow-plan-persistence";

const HISTORY_PAGE_LIMIT = 50;

type ReadyAssetState = {
  status: "ready";
  detail: WorkflowPlanDetail;
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
  const [retrySequence, setRetrySequence] = useState(0);
  const detailSequenceRef = useRef(0);
  const historySequenceRef = useRef(0);
  const historyControllerRef = useRef<AbortController | null>(null);
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

    void Promise.all([detailRequest, historyRequest])
      .then(([detail, history]) => {
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
          versions: history.items,
          total: history.total,
          nextOffset: history.offset + history.items.length,
          loadingMore: false,
          loadMoreError: null,
        });
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
