"use client";

import Link from "next/link";
import type { Route } from "next";
import { useEffect, useRef, useState } from "react";

import { useProjectSelection } from "@/components/layout/project-selection-provider";
import { listWorkflowPlans } from "@/lib/api/workflow-plan-persistence";
import type {
  WorkflowPlan,
  WorkflowPlanListResult,
} from "@/types/workflow-plan-persistence";

const PAGE_LIMIT = 20;

type WorkflowPlanListState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; result: WorkflowPlanListResult }
  | { status: "error"; message: string };

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function listErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "已保存计划暂不可用";
}

function assertListResponse(
  result: WorkflowPlanListResult,
  projectId: string,
  offset: number,
): void {
  const boundaryMismatch =
    result.projectStatus !== "active" ||
    result.limit !== PAGE_LIMIT ||
    result.offset !== offset ||
    result.databaseWrite !== false ||
    result.planChanged !== false ||
    result.providerCall !== false ||
    result.actorRun !== false ||
    result.browserRun !== false ||
    result.llmCall !== false ||
    result.workflowRunCreated !== false ||
    result.executionAuthorized !== false;
  const paginationMismatch =
    !Number.isInteger(result.total) ||
    result.total < 0 ||
    result.items.length > PAGE_LIMIT ||
    result.total < result.offset + result.items.length ||
    (result.items.length === 0 && result.offset < result.total);
  const projectMismatch = result.items.some(
    (item) => item.projectId !== projectId,
  );

  if (boundaryMismatch || paginationMismatch || projectMismatch) {
    throw new Error("WorkflowPlan list response context mismatch");
  }
}

function planDetailHref(projectId: string, planId: string): Route {
  return `/automation/projects/${encodeURIComponent(projectId)}/plans/${encodeURIComponent(planId)}` as Route;
}

export function SavedWorkflowPlansWorkspace() {
  const {
    selectedProject,
    loading: projectLoading,
    projectListError,
    markProjectFilterApplied,
    clearProjectFilterApplied,
  } = useProjectSelection();
  const projectId =
    selectedProject?.status === "active" ? selectedProject.id : null;

  return (
    <section
      aria-labelledby="saved-workflow-plans-heading"
      className="min-w-0 rounded-2xl border border-[#E9E5E2] bg-[#FFFDFC] p-4 sm:p-5"
      data-testid="saved-workflow-plans-workspace"
    >
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9A7467]">
          WorkflowPlan Assets
        </p>
        <h2
          className="mt-2 text-xl font-semibold text-[#2E201C]"
          id="saved-workflow-plans-heading"
        >
          Project 已保存计划
        </h2>
        <p className="mt-2 text-sm leading-6 text-[#716562]">
          这里展示只读摘要；打开详情后可审阅当前 Preview、Version History
          与结构化 Compare。
        </p>
      </div>

      <div className="mt-5 min-w-0">
        {projectLoading ? (
          <StatusMessage message="正在加载项目列表…" />
        ) : projectListError ? (
          <StatusMessage message={projectListError} role="alert" />
        ) : !projectId ? (
          <StatusMessage message="请先在顶部选择一个有效项目。" />
        ) : (
          <ActiveProjectWorkflowPlans
            clearProjectFilterApplied={clearProjectFilterApplied}
            key={projectId}
            markProjectFilterApplied={markProjectFilterApplied}
            projectId={projectId}
          />
        )}
      </div>
    </section>
  );
}

function ActiveProjectWorkflowPlans({
  projectId,
  markProjectFilterApplied,
  clearProjectFilterApplied,
}: {
  projectId: string;
  markProjectFilterApplied: (projectId: string) => void;
  clearProjectFilterApplied: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const [retrySequence, setRetrySequence] = useState(0);
  const [listState, setListState] = useState<WorkflowPlanListState>({
    status: "idle",
  });
  const requestSequenceRef = useRef(0);

  useEffect(() => {
    const sequence = requestSequenceRef.current + 1;
    requestSequenceRef.current = sequence;
    clearProjectFilterApplied();
    const controller = new AbortController();
    setListState({ status: "loading" });

    void listWorkflowPlans(projectId, {
      limit: PAGE_LIMIT,
      offset,
      signal: controller.signal,
    })
      .then((result) => {
        if (
          controller.signal.aborted ||
          requestSequenceRef.current !== sequence
        ) {
          return;
        }
        assertListResponse(result, projectId, offset);
        setListState({ status: "ready", result });
        markProjectFilterApplied(projectId);
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          requestSequenceRef.current !== sequence ||
          isAbortError(error)
        ) {
          return;
        }
        setListState({ status: "error", message: listErrorMessage(error) });
      });

    return () => {
      controller.abort();
      requestSequenceRef.current += 1;
      clearProjectFilterApplied();
    };
  }, [
    clearProjectFilterApplied,
    markProjectFilterApplied,
    offset,
    projectId,
    retrySequence,
  ]);

  return (
    <div
      aria-busy={listState.status === "loading"}
      className="min-w-0"
      data-testid="active-project-workflow-plans"
    >
      {listState.status === "loading" ? (
        <StatusMessage message="正在加载已保存计划…" />
      ) : listState.status === "error" ? (
        <div className="rounded-xl border border-[#E4B9A7] bg-[#FFF5EF] p-4">
          <p className="text-sm font-semibold text-[#803F32]" role="alert">
            {listState.message}
          </p>
          <button
            className="mt-3 rounded-xl border border-[#C97865] bg-white px-4 py-2 text-sm font-semibold text-[#8A4436]"
            onClick={() => setRetrySequence((current) => current + 1)}
            type="button"
          >
            重新加载
          </button>
        </div>
      ) : listState.status === "ready" &&
        listState.result.items.length === 0 ? (
        <StatusMessage message="当前项目还没有已保存计划。" />
      ) : listState.status === "ready" ? (
        <WorkflowPlanTable
          onNext={() => setOffset((current) => current + PAGE_LIMIT)}
          onPrevious={() =>
            setOffset((current) => Math.max(0, current - PAGE_LIMIT))
          }
          projectId={projectId}
          result={listState.result}
        />
      ) : null}
    </div>
  );
}

function StatusMessage({
  message,
  role = "status",
}: {
  message: string;
  role?: "alert" | "status";
}) {
  return (
    <p
      className="rounded-xl border border-[#E8DDD6] bg-white px-4 py-5 text-sm text-[#716562]"
      role={role}
    >
      {message}
    </p>
  );
}

function WorkflowPlanTable({
  projectId,
  result,
  onPrevious,
  onNext,
}: {
  projectId: string;
  result: WorkflowPlanListResult;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const hasPrevious = result.offset > 0;
  const hasNext = result.offset + result.limit < result.total;
  const firstItem = result.offset + 1;
  const lastItem = result.offset + result.items.length;

  return (
    <div className="min-w-0" data-testid="saved-workflow-plan-list">
      <div className="overflow-x-auto rounded-xl border border-[#E8DDD6] bg-white">
        <table className="min-w-[980px] w-full border-collapse text-left text-sm">
          <thead className="bg-[#FBF8F5] text-xs font-semibold uppercase tracking-[0.08em] text-[#7A625A]">
            <tr>
              <th className="px-4 py-3" scope="col">
                计划名称
              </th>
              <th className="px-4 py-3" scope="col">
                规划状态
              </th>
              <th className="px-4 py-3" scope="col">
                当前版本
              </th>
              <th className="px-4 py-3" scope="col">
                Scope
              </th>
              <th className="px-4 py-3" scope="col">
                QueryTerm
              </th>
              <th className="px-4 py-3" scope="col">
                最近更新
              </th>
              <th className="px-4 py-3" scope="col">
                创建者 ID
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#EFE7E2] text-[#4D3B36]">
            {result.items.map((plan) => (
              <WorkflowPlanRow
                key={plan.id}
                plan={plan}
                projectId={projectId}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-[#716562]">
          第 {firstItem}–{lastItem} 条，共 {result.total} 条
        </p>
        <div className="flex gap-2">
          <button
            className="rounded-xl border border-[#DCCFC8] bg-white px-4 py-2 text-sm font-semibold text-[#6D514A] disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!hasPrevious}
            onClick={onPrevious}
            type="button"
          >
            上一页
          </button>
          <button
            className="rounded-xl border border-[#DCCFC8] bg-white px-4 py-2 text-sm font-semibold text-[#6D514A] disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!hasNext}
            onClick={onNext}
            type="button"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  );
}

function WorkflowPlanRow({
  plan,
  projectId,
}: {
  plan: WorkflowPlan;
  projectId: string;
}) {
  return (
    <tr>
      <td className="px-4 py-3 font-semibold text-[#392823]">
        <Link
          className="underline decoration-[#D9B5A9] underline-offset-4 hover:text-[#8A4436]"
          href={planDetailHref(projectId, plan.id)}
        >
          {plan.name}
        </Link>
      </td>
      <td className="px-4 py-3">{plan.planningStatus}</td>
      <td className="px-4 py-3">v{plan.currentVersionNumber}</td>
      <td className="px-4 py-3 tabular-nums">{plan.scopeCount}</td>
      <td className="px-4 py-3 tabular-nums">{plan.queryTermCount}</td>
      <td className="px-4 py-3 whitespace-nowrap">
        <time dateTime={plan.updatedAt}>{plan.updatedAt}</time>
      </td>
      <td className="px-4 py-3 font-mono text-xs">{plan.createdByUserId}</td>
    </tr>
  );
}
