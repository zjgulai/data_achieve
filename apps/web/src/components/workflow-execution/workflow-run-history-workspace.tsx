"use client";

import {
  Activity,
  AlertTriangle,
  BookmarkCheck,
  CheckCircle2,
  Database,
  GitBranch,
  GitCompareArrows,
  Gauge,
  History,
  ListTree,
  Route,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { useProjectSelection } from "@/components/layout/project-selection-provider";
import {
  WorkbenchFact,
  WorkbenchPanel,
  WorkbenchStatusPill,
} from "@/components/common/workbench-ui";
import {
  createWorkflowRunAction,
  createWorkflowRunActionApproval,
  getWorkflowRun,
  getWorkflowRunAttemptFallbackEvidence,
  getWorkflowRunCheckpointBudgetEvidence,
  getWorkflowRunExecutorEvidence,
  getWorkflowRunActionGates,
  getWorkflowRunLineagePreview,
  getWorkflowRunProviderHealthEvidence,
  getWorkflowRunShadowComparisons,
  listWorkflowRuns,
  type WorkflowRunListOptions,
  type WorkflowRunTransport,
} from "@/lib/api/workflow-runs";
import type {
  WorkflowActionReceipt,
  WorkflowAttemptFallbackEvidence,
  WorkflowBudgetBlockerCode,
  WorkflowCheckpointBudgetEvidence,
  WorkflowCheckpointStepEvidence,
  WorkflowFallbackDecisionEvidence,
  WorkflowExecutorEvidence,
  WorkflowRun,
  WorkflowRunAction,
  WorkflowRunActionGateV2Evidence,
  WorkflowRunActionGates,
  WorkflowActionApprovalRequestDto,
  WorkflowRunActionRequestDto,
  WorkflowRunActionPreconditionBlockerCode,
  WorkflowRunActionPreconditionStatus,
  WorkflowRunActionNextActionCode,
  WorkflowRunDetail,
  WorkflowRunLineagePreview,
  WorkflowRunListResult,
  WorkflowProviderHealthEvidence,
  WorkflowProviderHealthStatus,
  WorkflowRunStatus,
  WorkflowShadowComparison,
  WorkflowShadowComparisonListResult,
  WorkflowStepAttemptEvidence,
} from "@/types/workflow-run";

const PAGE_LIMIT = 20;

type ListState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; result: WorkflowRunListResult }
  | { status: "error"; message: string };

type DetailState =
  | { status: "idle" }
  | { status: "loading" }
  | {
      status: "ready";
      result: WorkflowRunDetail;
      attemptFallbackEvidence: WorkflowAttemptFallbackEvidence;
      checkpointBudgetEvidence: WorkflowCheckpointBudgetEvidence;
      executorEvidence: WorkflowExecutorEvidence;
      providerHealthEvidence: WorkflowProviderHealthEvidence;
      actionGates: WorkflowRunActionGates;
      lineage: WorkflowRunLineagePreview;
      shadowComparisons: WorkflowShadowComparisonListResult;
    }
  | { status: "error"; message: string };

type MutationState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "success"; receipt: WorkflowActionReceipt }
  | { status: "error"; message: string };

export type WorkflowRunHistoryWorkspaceProps = {
  transport?: WorkflowRunTransport;
};

const defaultTransport: WorkflowRunTransport = {
  listRuns: listWorkflowRuns,
  getRun: getWorkflowRun,
  getAttemptFallbackEvidence: getWorkflowRunAttemptFallbackEvidence,
  getCheckpointBudgetEvidence: getWorkflowRunCheckpointBudgetEvidence,
  getProviderHealthEvidence: getWorkflowRunProviderHealthEvidence,
  getExecutorEvidence: getWorkflowRunExecutorEvidence,
  getActionGates: getWorkflowRunActionGates,
  createActionApproval: createWorkflowRunActionApproval,
  createAction: createWorkflowRunAction,
  getLineagePreview: getWorkflowRunLineagePreview,
  getShadowComparisons: getWorkflowRunShadowComparisons,
};

export function WorkflowRunHistoryWorkspace({
  transport = defaultTransport,
}: WorkflowRunHistoryWorkspaceProps) {
  const {
    selectedProject,
    loading: projectLoading,
    projectListError,
    markProjectFilterApplied,
    clearProjectFilterApplied,
  } = useProjectSelection();
  const projectId =
    selectedProject?.status === "active" ? selectedProject.id : null;
  const [pagination, setPagination] = useState<{
    projectId: string | null;
    offset: number;
  }>({ projectId: null, offset: 0 });
  const offset = pagination.projectId === projectId ? pagination.offset : 0;
  const updateOffset = (update: (current: number) => number) => {
    setPagination((current) => ({
      projectId,
      offset: update(current.projectId === projectId ? current.offset : 0),
    }));
  };
  const [retrySequence, setRetrySequence] = useState(0);
  const [listState, setListState] = useState<ListState>({ status: "idle" });
  const [selection, setSelection] = useState<{
    projectId: string;
    runId: string;
  } | null>(null);
  const selectedRunId =
    selection?.projectId === projectId ? selection.runId : null;
  const [detailState, setDetailState] = useState<DetailState>({
    status: "idle",
  });
  const [detailRefreshSequence, setDetailRefreshSequence] = useState(0);
  const [reviewGate, setReviewGate] =
    useState<WorkflowRunActionGateV2Evidence | null>(null);
  const [reviewReason, setReviewReason] = useState(
    "Cancel this held fixture Run after Owner review.",
  );
  const [mutationState, setMutationState] = useState<MutationState>({
    status: "idle",
  });
  const workspaceHeadingRef = useRef<HTMLHeadingElement | null>(null);
  const reviewTriggerRef = useRef<HTMLElement | null>(null);
  const listRequestSequence = useRef(0);
  const detailRequestSequence = useRef(0);

  useEffect(() => {
    if (!projectId) {
      setListState({ status: "idle" });
      setSelection(null);
      setDetailState({ status: "idle" });
      clearProjectFilterApplied();
      return;
    }

    const requestSequence = listRequestSequence.current + 1;
    listRequestSequence.current = requestSequence;
    const controller = new AbortController();
    setListState({ status: "loading" });
    clearProjectFilterApplied();

    const options: WorkflowRunListOptions = {
      limit: PAGE_LIMIT,
      offset,
      signal: controller.signal,
    };
    void transport
      .listRuns(projectId, options)
      .then((result) => {
        if (
          controller.signal.aborted ||
          requestSequence !== listRequestSequence.current
        ) {
          return;
        }
        assertListResponse(result, projectId, offset);
        setListState({ status: "ready", result });
        setSelection((current) =>
          current?.projectId === projectId &&
          result.items.some((item) => item.id === current.runId)
            ? current
            : null,
        );
        markProjectFilterApplied(projectId);
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          requestSequence !== listRequestSequence.current ||
          isAbortError(error)
        ) {
          return;
        }
        setListState({ status: "error", message: errorMessage(error) });
      });

    return () => {
      controller.abort();
      listRequestSequence.current += 1;
      clearProjectFilterApplied();
    };
  }, [
    clearProjectFilterApplied,
    markProjectFilterApplied,
    offset,
    projectId,
    retrySequence,
    transport,
  ]);

  useEffect(() => {
    if (!projectId || !selectedRunId) {
      setDetailState({ status: "idle" });
      return;
    }

    const requestSequence = detailRequestSequence.current + 1;
    detailRequestSequence.current = requestSequence;
    const controller = new AbortController();
    setDetailState({ status: "loading" });
    void Promise.all([
      transport.getRun(projectId, selectedRunId, { signal: controller.signal }),
      transport.getAttemptFallbackEvidence(projectId, selectedRunId, {
        signal: controller.signal,
      }),
      transport.getCheckpointBudgetEvidence(projectId, selectedRunId, {
        signal: controller.signal,
      }),
      transport.getProviderHealthEvidence(projectId, selectedRunId, {
        signal: controller.signal,
      }),
      transport.getExecutorEvidence(projectId, selectedRunId, {
        signal: controller.signal,
      }),
      transport.getActionGates(projectId, selectedRunId, {
        signal: controller.signal,
      }),
      transport.getLineagePreview(projectId, selectedRunId, {
        signal: controller.signal,
      }),
      transport.getShadowComparisons(projectId, selectedRunId, {
        signal: controller.signal,
      }),
    ])
      .then(
        ([
          result,
          attemptFallbackEvidence,
          checkpointBudgetEvidence,
          providerHealthEvidence,
          executorEvidence,
          actionGates,
          lineage,
          shadowComparisons,
        ]) => {
          if (
            controller.signal.aborted ||
            requestSequence !== detailRequestSequence.current
          ) {
            return;
          }
          assertDetailResponse(result, projectId, selectedRunId);
          assertAttemptFallbackEvidenceResponse(
            attemptFallbackEvidence,
            result,
            projectId,
            selectedRunId,
          );
          assertCheckpointBudgetEvidenceResponse(
            checkpointBudgetEvidence,
            result,
            projectId,
            selectedRunId,
          );
          assertProviderHealthEvidenceResponse(
            providerHealthEvidence,
            result,
            projectId,
            selectedRunId,
          );
          assertExecutorEvidenceResponse(
            executorEvidence,
            result,
            projectId,
            selectedRunId,
          );
          assertActionGatesResponse(
            actionGates,
            result,
            projectId,
            selectedRunId,
          );
          assertLineagePreviewResponse(lineage, projectId, selectedRunId);
          assertShadowComparisonResponse(
            shadowComparisons,
            projectId,
            selectedRunId,
          );
          setDetailState({
            status: "ready",
            result,
            attemptFallbackEvidence,
            checkpointBudgetEvidence,
            providerHealthEvidence,
            executorEvidence,
            actionGates,
            lineage,
            shadowComparisons,
          });
        },
      )
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          requestSequence !== detailRequestSequence.current ||
          isAbortError(error)
        ) {
          return;
        }
        setDetailState({ status: "error", message: errorMessage(error) });
      });

    return () => {
      controller.abort();
      detailRequestSequence.current += 1;
    };
  }, [detailRefreshSequence, projectId, selectedRunId, transport]);

  const closeReview = () => {
    setReviewGate(null);
    setMutationState({ status: "idle" });
    const trigger = reviewTriggerRef.current;
    reviewTriggerRef.current = null;
    if (trigger?.isConnected) {
      trigger.focus();
    } else {
      workspaceHeadingRef.current?.focus();
    }
  };

  const openReview = (
    gate: WorkflowRunActionGateV2Evidence,
    trigger: HTMLElement,
  ) => {
    reviewTriggerRef.current = trigger;
    setReviewGate(gate);
    setReviewReason("Cancel this held fixture Run after Owner review.");
    setMutationState({ status: "idle" });
  };

  const confirmReviewedAction = async () => {
    if (
      !projectId ||
      !selectedRunId ||
      !reviewGate ||
      reviewGate.action !== "cancel" ||
      detailState.status !== "ready" ||
      detailState.actionGates.schemaVersion !== "workflow_run_action_gates.v2"
    ) {
      return;
    }
    const actionGates = detailState.actionGates;
    const approvalPayload: WorkflowActionApprovalRequestDto = {
      schema_version: "workflow_action_approval_request.v1",
      action: "cancel",
      approval_kind: reviewGate.approvalKind,
      expected_action_context_version: actionGates.actionContextVersion,
      expected_run_status: actionGates.runStatus,
      action_gate_digest: actionGates.actionGateDigest,
      reason_code: "cancel_operator_request",
      reason: reviewReason,
      parameters: {
        action: "cancel",
        cancel_scope:
          actionGates.runStatus === "running" ? "running_run" : "held_run",
      },
    };
    setMutationState({ status: "submitting" });
    try {
      const approval = await transport.createActionApproval(
        projectId,
        selectedRunId,
        approvalPayload,
        nextWorkflowActionIdempotencyKey("approval"),
      );
      const actionPayload: WorkflowRunActionRequestDto = {
        schema_version: "workflow_run_action_request.v1",
        action: approvalPayload.action,
        expected_action_context_version:
          approvalPayload.expected_action_context_version,
        expected_run_status: approvalPayload.expected_run_status,
        action_gate_digest: approvalPayload.action_gate_digest,
        approval_receipt_id: approval.id,
        reason_code: approvalPayload.reason_code,
        reason: approvalPayload.reason,
        parameters: approvalPayload.parameters,
      };
      const receipt = await transport.createAction(
        projectId,
        selectedRunId,
        actionPayload,
        nextWorkflowActionIdempotencyKey("action"),
      );
      setMutationState({ status: "success", receipt });
      setDetailRefreshSequence((current) => current + 1);
    } catch (error: unknown) {
      setMutationState({ status: "error", message: errorMessage(error) });
      setDetailRefreshSequence((current) => current + 1);
    }
  };

  return (
    <section
      aria-labelledby="workflow-run-history-heading"
      className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 sm:p-5"
      data-testid="workflow-run-history-workspace"
      data-workflow-run-surface="evidence-and-review"
    >
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--action-primary)]">
            Workflow Execution / Evidence &amp; Review
          </p>
          <h2
            className="mt-2 text-xl font-semibold text-[var(--text-primary)]"
            id="workflow-run-history-heading"
            ref={workspaceHeadingRef}
            tabIndex={-1}
          >
            WorkflowRun 运行记录
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
            查看已记录的 fixture Run、不可变 Version lineage 与 StepRun
            证据；只有服务端 v2 门禁允许的本地动作可进入 Owner 评审。
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 rounded-[var(--radius-2)] border border-[var(--border-default)] bg-[var(--success-soft)] px-3 py-2 text-xs font-semibold text-[var(--state-success)]">
          <ShieldCheck aria-hidden="true" size={15} />
          <span>fixture-only / audited local action</span>
        </div>
      </div>

      <div className="mt-5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 text-sm leading-6 text-[var(--text-secondary)]">
        <span className="font-semibold text-[var(--text-primary)]">
          安全边界：
        </span>
        证据读取保持无副作用；仅经 v2 门禁和 Owner 收据的本地动作可写入动作审计。
        Provider、Credential、Browser、LLM、RawRecord、Dataset 与生产写入均为
        false。
      </div>

      <div className="mt-5">
        {projectLoading ? (
          <StatusMessage message="正在加载项目列表…" />
        ) : projectListError ? (
          <StatusMessage message={projectListError} role="alert" />
        ) : !projectId ? (
          <StatusMessage message="请先在顶部选择一个有效项目。" />
        ) : (
          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
            <RunListPanel
              listState={listState}
              onNext={() => updateOffset((current) => current + PAGE_LIMIT)}
              onPrevious={() =>
                updateOffset((current) => Math.max(0, current - PAGE_LIMIT))
              }
              onRetry={() => setRetrySequence((current) => current + 1)}
              onSelect={(runId) => setSelection({ projectId, runId })}
              selectedRunId={selectedRunId}
            />
            <RunDetailPanel
              detailState={detailState}
              onReviewAction={openReview}
            />
          </div>
        )}
      </div>
      {reviewGate && detailState.status === "ready" ? (
        <WorkflowActionReviewDrawer
          detail={detailState.result}
          gate={reviewGate}
          mutationState={mutationState}
          onClose={closeReview}
          onConfirm={confirmReviewedAction}
          onReasonChange={setReviewReason}
          reason={reviewReason}
        />
      ) : null}
    </section>
  );
}

function RunListPanel({
  listState,
  onNext,
  onPrevious,
  onRetry,
  onSelect,
  selectedRunId,
}: {
  listState: ListState;
  onNext: () => void;
  onPrevious: () => void;
  onRetry: () => void;
  onSelect: (runId: string) => void;
  selectedRunId: string | null;
}) {
  return (
    <WorkbenchPanel
      icon={ListTree}
      label="Run history"
      subtitle="稳定分页，只读历史"
      title="运行列表"
    >
      {listState.status === "loading" ? (
        <StatusMessage message="正在加载 fixture Run…" />
      ) : listState.status === "error" ? (
        <div className="rounded-xl border border-[#E4B9A7] bg-[#FFF5EF] p-4">
          <p className="text-sm font-semibold text-[#803F32]" role="alert">
            {listState.message}
          </p>
          <button
            className="mt-3 rounded-xl border border-[#C97865] bg-white px-4 py-2 text-sm font-semibold text-[#8A4436]"
            onClick={onRetry}
            type="button"
          >
            重新加载
          </button>
        </div>
      ) : listState.status === "ready" &&
        listState.result.items.length === 0 ? (
        <StatusMessage message="当前项目还没有 fixture Run 记录。" />
      ) : listState.status === "ready" ? (
        <>
          <div className="grid gap-2" data-testid="workflow-run-list">
            {listState.result.items.map((run) => (
              <RunListItem
                key={run.id}
                onSelect={onSelect}
                run={run}
                selected={run.id === selectedRunId}
              />
            ))}
          </div>
          <div className="mt-4 flex flex-col gap-3 border-t border-[#F0E1D9] pt-4 text-sm text-[#716562] sm:flex-row sm:items-center sm:justify-between">
            <span>
              第 {listState.result.offset + 1}–
              {listState.result.offset + listState.result.items.length} 条，共{" "}
              {listState.result.total} 条
            </span>
            <div className="flex gap-2">
              <button
                className="rounded-lg border border-[#E8DDD6] bg-white px-3 py-1.5 text-xs font-semibold text-[#6C5B55] disabled:cursor-not-allowed disabled:opacity-40"
                disabled={listState.result.offset === 0}
                onClick={onPrevious}
                type="button"
              >
                上一页
              </button>
              <button
                className="rounded-lg border border-[#E8DDD6] bg-white px-3 py-1.5 text-xs font-semibold text-[#6C5B55] disabled:cursor-not-allowed disabled:opacity-40"
                disabled={
                  listState.result.offset + listState.result.items.length >=
                  listState.result.total
                }
                onClick={onNext}
                type="button"
              >
                下一页
              </button>
            </div>
          </div>
        </>
      ) : null}
    </WorkbenchPanel>
  );
}

function RunListItem({
  onSelect,
  run,
  selected,
}: {
  onSelect: (runId: string) => void;
  run: WorkflowRun;
  selected: boolean;
}) {
  return (
    <div
      className={
        selected
          ? "rounded-xl border border-[#C96F5C] bg-[#FFF5F0]"
          : "rounded-xl border border-[#F0E1D9] bg-[#FFFDFC]"
      }
      data-workflow-run-id={run.id}
    >
      <button
        aria-pressed={selected}
        className="w-full px-3 py-3 text-left transition hover:bg-[#FFF5F0]"
        onClick={() => onSelect(run.id)}
        type="button"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[#3B2924]">
              {run.id}
            </p>
            <p className="mt-1 text-xs text-[#8A7770]">
              {run.fixtureProfileId} · Version {shortId(run.workflowVersionId)}
            </p>
          </div>
          <StatusBadge status={run.status} />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-[#716562]">
          <span>
            Steps {run.completedSteps}/{run.totalSteps}
          </span>
          <span>Records {run.recordsCount}</span>
          <span className="text-right">{formatTimestamp(run.createdAt)}</span>
        </div>
      </button>
    </div>
  );
}

function RunDetailPanel({
  detailState,
  onReviewAction,
}: {
  detailState: DetailState;
  onReviewAction: (
    gate: WorkflowRunActionGateV2Evidence,
    trigger: HTMLElement,
  ) => void;
}) {
  return (
    <WorkbenchPanel
      icon={GitBranch}
      label="Frozen evidence"
      subtitle="Version-derived lineage"
      title="Run 详情"
    >
      {detailState.status === "idle" ? (
        <StatusMessage message="选择一个 Run 查看冻结的 Template/Revision lineage 与 StepRun 证据。" />
      ) : detailState.status === "loading" ? (
        <StatusMessage message="正在加载 Run 详情…" />
      ) : detailState.status === "error" ? (
        <StatusMessage message={detailState.message} role="alert" />
      ) : (
        <RunDetailContent
          actionGates={detailState.actionGates}
          attemptFallbackEvidence={detailState.attemptFallbackEvidence}
          checkpointBudgetEvidence={detailState.checkpointBudgetEvidence}
          detail={detailState.result}
          executorEvidence={detailState.executorEvidence}
          lineage={detailState.lineage}
          providerHealthEvidence={detailState.providerHealthEvidence}
          shadowComparisons={detailState.shadowComparisons}
          onReviewAction={onReviewAction}
        />
      )}
    </WorkbenchPanel>
  );
}

function RunDetailContent({
  actionGates,
  attemptFallbackEvidence,
  checkpointBudgetEvidence,
  detail,
  executorEvidence,
  lineage,
  onReviewAction,
  providerHealthEvidence,
  shadowComparisons,
}: {
  actionGates: WorkflowRunActionGates;
  attemptFallbackEvidence: WorkflowAttemptFallbackEvidence;
  checkpointBudgetEvidence: WorkflowCheckpointBudgetEvidence;
  detail: WorkflowRunDetail;
  executorEvidence: WorkflowExecutorEvidence;
  lineage: WorkflowRunLineagePreview;
  onReviewAction: (
    gate: WorkflowRunActionGateV2Evidence,
    trigger: HTMLElement,
  ) => void;
  providerHealthEvidence: WorkflowProviderHealthEvidence;
  shadowComparisons: WorkflowShadowComparisonListResult;
}) {
  const { run } = detail;
  return (
    <div className="grid gap-4" data-testid="workflow-run-detail">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-all text-sm font-semibold text-[#3B2924]">
            {run.id}
          </p>
          <p className="mt-1 text-xs text-[#8A7770]">
            {run.executionContractVersion}
          </p>
        </div>
        <StatusBadge status={run.status} />
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <WorkbenchFact label="Fixture profile" value={run.fixtureProfileId} />
        <WorkbenchFact label="Records" value={String(run.recordsCount)} />
        <WorkbenchFact label="Version" value={run.workflowVersionId} />
        <WorkbenchFact label="Plan" value={run.workflowPlanId} />
      </div>

      {run.statusReasonCode && run.impactCode ? (
        <section
          aria-label="运行状态说明"
          className="rounded-[var(--radius-3)] border border-[var(--state-warning)] bg-[var(--warning-soft)] p-4"
        >
          <div className="flex items-start gap-3">
            <span className="mt-0.5 text-[var(--state-warning)]">
              <AlertTriangle aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                {statusLabel(run.status)}
              </p>
              <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                状态来自冻结的运行证据；本区仅说明原因、影响与允许的恢复方向，不会触发执行。
              </p>
            </div>
          </div>
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            <StateFact
              label="状态事实"
              value={reasonLabel(run.statusReasonCode)}
            />
            <StateFact label="业务影响" value={impactLabel(run.impactCode)} />
            <StateFact
              label="下一步"
              value={
                run.recoveryActionCodes.length > 0
                  ? run.recoveryActionCodes.map(recoveryActionLabel).join("；")
                  : "无需恢复操作"
              }
            />
          </dl>
          {run.missingFields.length > 0 ? (
            <div className="mt-4 border-t border-[var(--border-subtle)] pt-3">
              <p className="text-xs font-semibold text-[var(--text-secondary)]">
                缺失字段
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {run.missingFields.map((field) => (
                  <code
                    className="rounded-[var(--radius-pill)] bg-[var(--surface-primary)] px-2.5 py-1 text-xs text-[var(--state-danger)]"
                    key={field}
                  >
                    {field}
                  </code>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="rounded-xl border border-[#E8D4CB] bg-[#FFF8F4] p-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#4D3B36]">
          <GitBranch aria-hidden="true" size={15} />
          Template / Revision lineage
        </div>
        {run.workflowTemplateId && run.workflowTemplateRevisionId ? (
          <div className="mt-3 grid gap-2 text-xs text-[#716562]">
            <p className="break-all">Template: {run.workflowTemplateId}</p>
            <p className="break-all">
              Revision: {run.workflowTemplateRevisionId}
            </p>
          </div>
        ) : (
          <p className="mt-2 text-sm text-[#8A7770]">
            未关联 Template Revision（pair 为 null）。
          </p>
        )}
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <BoundaryFact
          icon={Database}
          label="Database write"
          value={String(detail.databaseWrite)}
        />
        <BoundaryFact
          icon={Activity}
          label="Provider call"
          value={String(detail.providerCall)}
        />
        <BoundaryFact
          icon={ShieldCheck}
          label="Live authorized"
          value={String(detail.liveExecutionAuthorized)}
        />
      </div>

      <div className="rounded-xl border border-[#E8D4CB] bg-[#FFF8F4] p-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#4D3B36]">
          <Database aria-hidden="true" size={15} />
          Provider / RawRecord / Dataset lineage preview
        </div>
        <p className="mt-2 text-xs leading-5 text-[#716562]">
          {lineage.rawRecord.materialized && lineage.dataset.materialized
            ? "已生成 RawRecord 与 Dataset 实体；本页只读展示对应 lineage。"
            : "仅把 StepRun 的 fixture evidence 映射为待物化意图；当前没有 RawRecord 或 Dataset 实体。"}
        </p>
        <div className="mt-3 grid gap-2 text-xs text-[#716562] sm:grid-cols-3">
          <LineageFact
            label="Provider evidence"
            value={String(lineage.providerEvidence.length)}
          />
          <LineageFact
            label="RawRecord"
            value={
              lineage.rawRecord.materialized
                ? "materialized"
                : "not materialized"
            }
          />
          <LineageFact
            label="Dataset"
            value={
              lineage.dataset.materialized ? "materialized" : "not materialized"
            }
          />
        </div>
        <div className="mt-3 grid gap-2 text-xs text-[#8A7770]">
          <span>
            RawRecord blocker：{lineage.rawRecord.blockedReasons.join("、")}
          </span>
          <span>
            Dataset blocker：{lineage.dataset.blockedReasons.join("、")}
          </span>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <WorkbenchFact label="Started" value={formatTimestamp(run.startedAt)} />
        <WorkbenchFact
          label="Finished"
          value={formatTimestamp(run.finishedAt)}
        />
      </div>

      <ExecutorEvidencePanel result={executorEvidence} />

      <RunActionGatesPanel
        onReviewAction={onReviewAction}
        result={actionGates}
      />

      <AttemptFallbackEvidencePanel
        detail={detail}
        result={attemptFallbackEvidence}
      />

      <CheckpointBudgetEvidencePanel result={checkpointBudgetEvidence} />

      <ProviderHealthEvidencePanel result={providerHealthEvidence} />

      <ShadowComparisonPanel result={shadowComparisons} />

      <div className="grid gap-2">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#4D3B36]">
          <ListTree aria-hidden="true" size={15} />
          StepRun 证据
        </div>
        {detail.steps.map((step) => (
          <div
            className="rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3"
            key={step.id}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-[#3B2924]">
                  {step.sequence}. {step.stepRef}
                </p>
                <p className="mt-1 text-xs text-[#8A7770]">
                  {step.platform} / {step.operation} ·{" "}
                  {step.fixtureCaseId ?? "未生成 fixture receipt"}
                </p>
              </div>
              <span
                className={
                  step.status === "completed"
                    ? "shrink-0 text-xs font-semibold text-[var(--state-success)]"
                    : step.status === "failed"
                      ? "shrink-0 text-xs font-semibold text-[var(--state-danger)]"
                      : "shrink-0 text-xs font-semibold text-[var(--state-warning)]"
                }
              >
                {stepStatusLabel(step.status)}
              </span>
            </div>
            <div className="mt-3 grid gap-2 text-xs text-[#716562] sm:grid-cols-2">
              <span>证据引用：{step.evidenceRefs.join(", ")}</span>
              <span>Records：{step.recordsCount}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 rounded-xl bg-[#F4FBF6] px-3 py-2 text-xs font-semibold text-[#2A7A4B]">
        <CheckCircle2 aria-hidden="true" size={14} />
        本详情只呈现 fixture receipt，不产生外部副作用。
      </div>
    </div>
  );
}

function ExecutorEvidencePanel({
  result,
}: {
  result: WorkflowExecutorEvidence;
}) {
  const latestDispatch = result.dispatches.at(-1) ?? null;
  const leaseLabel = latestDispatch?.lease
    ? latestDispatch.lease.fresh
      ? "租约有效"
      : "租约已过期或不可用"
    : "尚无租约";
  const preflightLabel =
    latestDispatch?.preflightState === "eligible"
      ? "预检通过，仍缺精确授权"
      : latestDispatch?.preflightState === "blocked"
        ? "预检已阻断"
        : "尚未执行预检";
  const cancellationLabel = latestDispatch?.cancellation.requested
    ? latestDispatch.cancellation.acknowledged
      ? "取消意图已确认"
      : "取消意图待 Worker 确认"
    : "尚无取消意图";
  return (
    <section
      aria-labelledby="workflow-executor-evidence-heading"
      className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4"
      data-testid="workflow-executor-evidence"
    >
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 text-[var(--state-info)]">
            <Activity aria-hidden="true" size={18} />
          </span>
          <div className="min-w-0">
            <h3
              className="text-sm font-semibold text-[var(--text-primary)]"
              id="workflow-executor-evidence-heading"
            >
              执行器证据与授权边界
            </h3>
            <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
              展示已持久化的派发、租约、预检、CallAudit 与取消确认；动作收据只代表命令被接受，不代表执行已开始。
            </p>
          </div>
        </div>
        <WorkbenchStatusPill status="fixture-local" tone="amber">
          L2 fixture
        </WorkbenchStatusPill>
      </div>

      <div className="mt-4 rounded-[var(--radius-2)] border border-[var(--state-warning)] bg-[var(--warning-soft)] p-3">
        <p className="text-sm font-semibold text-[var(--text-primary)]">
          {executorCauseLabel(result.businessCauseCode)}
        </p>
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
          <StateFact
            label="业务影响"
            value={executorImpactLabel(result.businessImpactCode)}
          />
          <StateFact
            label="下一步"
            value={executorNextActionLabel(result.nextActionCode)}
          />
        </dl>
        <p className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">
          当前不会读取 Credential、构建官方 Client 或发起 Provider/网络调用。运行中取消仍保持禁用，直到当前 Worker 的持久化 acknowledgement 与独立 live 门禁同时存在。
        </p>
      </div>

      <dl className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <StateFact label="Dispatch" value={`${result.dispatchTotal} 条`} />
        <StateFact label="Lease" value={leaseLabel} />
        <StateFact label="Preflight" value={preflightLabel} />
        <StateFact
          label="CallAudit"
          value={`${latestDispatch?.auditTotal ?? 0} 条`}
        />
        <StateFact label="取消状态" value={cancellationLabel} />
      </dl>

      {result.dispatches.length === 0 ? (
        <EvidenceEmptyState>
          尚无执行器派发证据。请先核对动作收据与 dispatch 门禁；本页不会自动补建或启动执行。
        </EvidenceEmptyState>
      ) : (
        <div className="mt-4 grid gap-3">
          {result.dispatches.map((dispatch) => (
            <div
              className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3"
              key={dispatch.id}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  Generation {dispatch.attemptGeneration} · {dispatch.state}
                </p>
                <WorkbenchStatusPill
                  status={dispatch.preflightState}
                  tone={
                    dispatch.preflightState === "blocked"
                      ? "red"
                      : dispatch.preflightState === "eligible"
                        ? "amber"
                        : "neutral"
                  }
                >
                  {dispatch.preflightState}
                </WorkbenchStatusPill>
              </div>
              <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">
                {dispatch.cancellation.requested &&
                !dispatch.cancellation.acknowledged
                  ? "Owner 取消意图已记录，但尚无 Worker acknowledgement；不得显示为已取消。"
                  : "当前证据不会推断 live Provider 成功或外部副作用。"}
              </p>
              <details className="mt-3 border-t border-[var(--border-subtle)] pt-2">
                <summary className="flex min-h-[var(--touch-target)] cursor-pointer items-center text-sm font-semibold text-[var(--action-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]">
                  Advanced diagnostics
                </summary>
                <dl className="grid gap-2 pb-1 sm:grid-cols-2">
                  <StateFact label="Dispatch ID" value={dispatch.id} />
                  <StateFact
                    label="StepRun ID"
                    value={dispatch.workflowStepRunId}
                  />
                  <StateFact
                    label="Fencing token"
                    value={
                      dispatch.lease
                        ? String(dispatch.lease.fencingToken)
                        : "not issued"
                    }
                  />
                  <StateFact
                    label="Credential permit"
                    value={dispatch.credentialPermitIds.join(", ") || "not issued"}
                  />
                  <StateFact
                    label="Provider permit"
                    value={dispatch.providerPermitIds.join(", ") || "not issued"}
                  />
                  <StateFact
                    label="Audit IDs"
                    value={
                      dispatch.audits.map((audit) => audit.id).join(", ") ||
                      "not recorded"
                    }
                  />
                  <StateFact
                    label="Provider / operation"
                    value={
                      dispatch.audits
                        .map(
                          (audit) => `${audit.providerId} / ${audit.operationId}`,
                        )
                        .join(", ") || "not attempted"
                    }
                  />
                  <StateFact
                    label="Last event"
                    value={dispatch.lastEvent?.eventType ?? "not recorded"}
                  />
                </dl>
              </details>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function RunActionGatesPanel({
  onReviewAction,
  result,
}: {
  onReviewAction: (
    gate: WorkflowRunActionGateV2Evidence,
    trigger: HTMLElement,
  ) => void;
  result: WorkflowRunActionGates;
}) {
  const currentContract =
    result.schemaVersion === "workflow_run_action_gates.v2";
  return (
    <section
      aria-labelledby="workflow-run-action-gates-heading"
      className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4"
      data-testid="workflow-run-action-gates"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-[var(--accent-primary)]">
          <ShieldCheck aria-hidden="true" size={18} />
        </span>
        <div className="min-w-0 flex-1">
          <h3
            className="text-sm font-semibold text-[var(--text-primary)]"
            id="workflow-run-action-gates-heading"
          >
            下一步操作门禁
          </h3>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            {currentContract
              ? "服务器按当前证据计算可评审动作；任何本地变更都必须先打开审核抽屉并取得 Owner 收据。"
              : "只读评估重试、恢复、取消、预算覆盖与路线切换。当前 v1 合同不提供任何变更入口。"}
          </p>
        </div>
        <WorkbenchStatusPill
          status={currentContract ? "review-gated" : "read-only"}
          tone={result.availableActionTotal > 0 ? "amber" : "neutral"}
        >
          可评审 {result.availableActionTotal}
        </WorkbenchStatusPill>
      </div>

      <dl className="mt-4 grid gap-2 sm:grid-cols-3">
        <StateFact
          label="可进入评审"
          value={`${result.readyForReviewTotal} 项`}
        />
        <StateFact label="已阻断" value={`${result.blockedTotal} 项`} />
        <StateFact
          label="当前不适用"
          value={`${result.notApplicableTotal} 项`}
        />
      </dl>

      <div className="mt-4 grid gap-2">
        {result.schemaVersion === "workflow_run_action_gates.v1"
          ? result.gates.map((gate) => (
              <article
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3"
                key={gate.action}
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[var(--text-primary)]">
                      {runActionLabel(gate.action)}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                      {gate.preconditionBlockerCodes.length > 0
                        ? gate.preconditionBlockerCodes
                            .map(runActionBlockerLabel)
                            .join("；")
                        : "前置证据已满足，但 v1 仍保持只读。"}
                    </p>
                  </div>
                  <WorkbenchStatusPill
                    status={gate.preconditionStatus}
                    tone={
                      gate.preconditionStatus === "ready_for_review"
                        ? "amber"
                        : gate.preconditionStatus === "blocked"
                          ? "red"
                          : "neutral"
                    }
                  >
                    {runActionPreconditionLabel(gate.preconditionStatus)}
                  </WorkbenchStatusPill>
                </div>
                <p className="mt-2 text-xs font-medium text-[var(--text-primary)]">
                  建议下一步：{runActionNextLabel(gate.nextActionCode)}
                </p>
                <p className="mt-1 text-xs text-[var(--state-danger)]">
                  当前不可执行：v1 未开放变更端点与持久化动作审计。
                </p>
                <ActionGateDiagnostics gate={gate} />
              </article>
            ))
          : result.gates.map((gate) => {
              const clientSupported = gate.action === "cancel";
              const disabled =
                !gate.submissionAvailable || !clientSupported;
              const blockerText =
                gate.preconditionBlockerCodes.length > 0
                  ? gate.preconditionBlockerCodes
                      .map(runActionBlockerLabel)
                      .join("；")
                  : gate.availabilityBlockerCodes.length > 0
                    ? gate.availabilityBlockerCodes.join("；")
                    : clientSupported
                      ? "当前证据满足，可进入 Owner 审核。"
                      : "服务端已开放，但当前客户端尚无严格参数构造器。";
              return (
                <article
                  className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3"
                  key={gate.action}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-[var(--text-primary)]">
                        {runActionLabel(gate.action)}
                      </p>
                      <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                        {blockerText}
                      </p>
                    </div>
                    <WorkbenchStatusPill
                      status={
                        gate.submissionAvailable
                          ? "review-ready"
                          : gate.preconditionStatus
                      }
                      tone={gate.submissionAvailable ? "amber" : "neutral"}
                    >
                      {gate.submissionAvailable
                        ? "等待审核"
                        : runActionPreconditionLabel(gate.preconditionStatus)}
                    </WorkbenchStatusPill>
                  </div>
                  <button
                    className="mt-3 min-h-[var(--touch-target)] w-full rounded-[var(--radius-2)] border border-[var(--border-strong)] bg-[var(--surface-primary)] px-3 py-2 text-sm font-semibold text-[var(--text-primary)] transition hover:border-[var(--accent-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={disabled}
                    onClick={(event) =>
                      onReviewAction(gate, event.currentTarget)
                    }
                    type="button"
                  >
                    {disabled ? "当前不可评审" : "打开审核"}
                  </button>
                  <ActionGateDiagnostics gate={gate} />
                </article>
              );
            })}
      </div>

      <p className="mt-4 border-t border-[var(--border-subtle)] pt-3 text-xs leading-5 text-[var(--text-secondary)]">
        判定基于冻结运行状态、尝试与回退、断点与预算、Provider Health
        证据。审核收据只写入本地动作审计；不会调用 Provider、读取凭证、启动执行器或写入生产。
      </p>
    </section>
  );
}

function ActionGateDiagnostics({
  gate,
}: {
  gate:
    | WorkflowRunActionGates["gates"][number]
    | WorkflowRunActionGateV2Evidence;
}) {
  return (
    <details className="mt-2 text-xs text-[var(--text-secondary)]">
      <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
        查看门禁诊断
      </summary>
      <dl className="mt-2 grid gap-2">
        <ShadowDiagnosticFact
          label="Precondition blockers"
          value={gate.preconditionBlockerCodes.join("、") || "none"}
        />
        <ShadowDiagnosticFact
          label="Availability blockers"
          value={gate.availabilityBlockerCodes.join("、") || "none"}
        />
        <ShadowDiagnosticFact
          label="Evidence refs"
          value={gate.evidenceRefs.join("、")}
        />
      </dl>
    </details>
  );
}

function WorkflowActionReviewDrawer({
  detail,
  gate,
  mutationState,
  onClose,
  onConfirm,
  onReasonChange,
  reason,
}: {
  detail: WorkflowRunDetail;
  gate: WorkflowRunActionGateV2Evidence;
  mutationState: MutationState;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  onReasonChange: (value: string) => void;
  reason: string;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusable = dialog.querySelectorAll<HTMLElement>(
      'button:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
    );
    focusable[0]?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    dialog.addEventListener("keydown", handleKeyDown);
    return () => dialog.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const submitting = mutationState.status === "submitting";
  return (
    <div
      className="fixed inset-0 z-50 flex items-end bg-[color:var(--overlay-scrim)] sm:items-stretch sm:justify-end"
      data-testid="workflow-action-review-overlay"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target && !submitting) onClose();
      }}
    >
      <div
        aria-describedby="workflow-action-review-description"
        aria-labelledby="workflow-action-review-title"
        aria-modal="true"
        className="flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-[var(--radius-4)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] shadow-[var(--shadow-overlay)] sm:max-h-none sm:max-w-md sm:rounded-none sm:border-y-0 sm:border-r-0"
        ref={dialogRef}
        role="dialog"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--border-subtle)] p-4 sm:p-5">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--accent-primary)]">
              Owner action review
            </p>
            <h2
              className="mt-2 text-lg font-semibold text-[var(--text-primary)]"
              id="workflow-action-review-title"
            >
              审核{runActionLabel(gate.action)}
            </h2>
            <p
              className="mt-2 text-sm leading-6 text-[var(--text-secondary)]"
              id="workflow-action-review-description"
            >
              确认后先签发短时审批收据，再提交一次本地 fixture 动作。
            </p>
          </div>
          <button
            aria-label="关闭动作审核"
            className="flex h-[var(--touch-target)] w-[var(--touch-target)] shrink-0 items-center justify-center rounded-[var(--radius-2)] border border-[var(--border-subtle)] text-[var(--text-secondary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
            disabled={submitting}
            onClick={onClose}
            type="button"
          >
            <X aria-hidden="true" size={18} />
          </button>
        </div>

        <div className="grid flex-1 gap-4 overflow-y-auto p-4 sm:p-5">
          <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-3">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              影响范围
            </h3>
            <dl className="mt-3 grid gap-2">
              <StateFact label="Run" value={detail.run.id} />
              <StateFact
                label="Steps"
                value={detail.steps
                  .map((step) => `${step.sequence}. ${step.stepRef} · ${step.status}`)
                  .join("；")}
              />
              <StateFact label="当前状态" value={detail.run.status} />
            </dl>
          </section>

          <section className="rounded-[var(--radius-3)] border border-[var(--state-warning)] bg-[var(--warning-soft)] p-3">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              将发生
            </h3>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              held Run 将记录为 cancelled，并写入不可变请求、收据与审计链。
            </p>
          </section>

          <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-3">
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">
              不会发生
            </h3>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              不调用 Provider、不读取 Credential、不启动执行器、不写入
              RawRecord/Dataset，也不触碰生产环境。
            </p>
          </section>

          <label className="grid gap-2 text-sm font-semibold text-[var(--text-primary)]">
            审核理由
            <textarea
              aria-describedby="workflow-action-reason-help"
              className="min-h-24 rounded-[var(--radius-2)] border border-[var(--border-strong)] bg-[var(--surface-primary)] px-3 py-2 text-sm font-normal leading-6 text-[var(--text-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
              disabled={submitting || mutationState.status === "success"}
              maxLength={500}
              minLength={1}
              onChange={(event) => onReasonChange(event.target.value)}
              value={reason}
            />
          </label>
          <p
            className="text-xs leading-5 text-[var(--text-secondary)]"
            id="workflow-action-reason-help"
          >
            审批类型：{gate.approvalKind}；收据将在{" "}
            {formatTimestamp(gate.expiresAt)} 前有效。
          </p>

          <details className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] p-3 text-xs text-[var(--text-secondary)]">
            <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
              证据诊断
            </summary>
            <p className="mt-2 break-all leading-5">
              {gate.evidenceRefs.join("；")}
            </p>
          </details>

          {mutationState.status === "error" ? (
            <div
              className="rounded-[var(--radius-2)] border border-[var(--state-danger)] bg-[var(--danger-soft)] p-3 text-sm text-[var(--state-danger)]"
              role="alert"
            >
              {mutationState.message}。已刷新 Run 与全部子证据，请重新审核。
            </div>
          ) : null}
          {mutationState.status === "success" ? (
            <div
              className="rounded-[var(--radius-2)] border border-[var(--state-success)] bg-[var(--success-soft)] p-3"
              role="status"
            >
              <p className="text-sm font-semibold text-[var(--state-success)]">
                本地动作已记录
              </p>
              <p className="mt-2 break-all text-xs leading-5 text-[var(--text-secondary)]">
                Receipt {mutationState.receipt.id} ·{" "}
                {mutationState.receipt.afterRunStatus} · context{" "}
                {mutationState.receipt.afterActionContextVersion}
              </p>
            </div>
          ) : null}
        </div>

        <div className="grid gap-2 border-t border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 sm:grid-cols-2 sm:p-5">
          <button
            className="min-h-[var(--touch-target)] rounded-[var(--radius-2)] border border-[var(--border-strong)] px-4 py-2 text-sm font-semibold text-[var(--text-primary)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
            disabled={submitting}
            onClick={onClose}
            type="button"
          >
            {mutationState.status === "success" ? "完成" : "返回"}
          </button>
          {mutationState.status !== "success" ? (
            <button
              className="min-h-[var(--touch-target)] rounded-[var(--radius-2)] bg-[var(--accent-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-50"
              disabled={submitting || reason.trim().length === 0}
              onClick={() => void onConfirm()}
              type="button"
            >
              {submitting ? "正在签发并提交…" : "确认并记录本地动作"}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function AttemptFallbackEvidencePanel({
  detail,
  result,
}: {
  detail: WorkflowRunDetail;
  result: WorkflowAttemptFallbackEvidence;
}) {
  const attemptedStepIds = new Set(
    result.attempts.map((item) => item.stepRunId),
  );
  const retriedStepCount = new Set(
    result.attempts
      .filter((item) => item.attemptNumber > 1)
      .map((item) => item.stepRunId),
  ).size;
  return (
    <section
      aria-labelledby="workflow-attempt-fallback-heading"
      className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4"
      data-testid="workflow-attempt-fallback-evidence"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-[var(--state-info)]">
          <History aria-hidden="true" size={18} />
        </span>
        <div className="min-w-0">
          <h3
            className="text-sm font-semibold text-[var(--text-primary)]"
            id="workflow-attempt-fallback-heading"
          >
            尝试记录与备用路线判断
          </h3>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            展示已持久化的 Step 尝试结果与 Fallback
            门判断；本区不会重试、切换路线或调用 Provider。
          </p>
        </div>
      </div>

      <dl className="mt-4 grid gap-2 sm:grid-cols-3">
        <StateFact
          label="已有尝试的步骤"
          value={`${attemptedStepIds.size} 个`}
        />
        <StateFact label="发生重试的步骤" value={`${retriedStepCount} 个`} />
        <StateFact
          label="Fallback 判断"
          value={`${result.fallbackDecisionTotal} 条`}
        />
      </dl>

      <div className="mt-4 border-t border-[var(--border-subtle)] pt-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <History aria-hidden="true" size={15} />
          Step 尝试时间线
        </div>
        {result.attempts.length === 0 ? (
          <p className="mt-3 rounded-[var(--radius-2)] border border-dashed border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-4 text-sm text-[var(--text-secondary)]">
            当前 Run 没有 Step Attempt
            证据；这不代表步骤从未尝试，也不会触发自动补跑。
          </p>
        ) : (
          <div className="mt-3 grid gap-3">
            {detail.steps.map((step) => {
              const attempts = result.attempts
                .filter((item) => item.stepRunId === step.id)
                .sort(
                  (left, right) => left.attemptNumber - right.attemptNumber,
                );
              return attempts.length > 0 ? (
                <StepAttemptEvidenceCard
                  attempts={attempts}
                  key={step.id}
                  stepLabel={`${step.sequence}. ${step.stepRef}`}
                />
              ) : null;
            })}
          </div>
        )}
      </div>

      <div className="mt-4 border-t border-[var(--border-subtle)] pt-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <Route aria-hidden="true" size={15} />
          Fallback 决策
        </div>
        {result.fallbackDecisions.length === 0 ? (
          <p className="mt-3 rounded-[var(--radius-2)] border border-dashed border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-4 text-sm text-[var(--text-secondary)]">
            当前 Run 没有 Fallback
            决策证据；不会推断备用路线可用，也不会自动切换。
          </p>
        ) : (
          <div className="mt-3 grid gap-3">
            {result.fallbackDecisions.map((decision) => (
              <FallbackDecisionEvidenceCard
                decision={decision}
                key={decision.id}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function StepAttemptEvidenceCard({
  attempts,
  stepLabel,
}: {
  attempts: WorkflowStepAttemptEvidence[];
  stepLabel: string;
}) {
  const finalAttempt = attempts.at(-1)!;
  return (
    <article className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="break-all text-sm font-semibold text-[var(--text-primary)]">
            {stepLabel}
          </p>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            共 {attempts.length} 次尝试；最终结果：
            {attemptStatusLabel(finalAttempt.status)}。
            {finalAttempt.errorCode
              ? ` 原因：${attemptErrorLabel(finalAttempt.errorCode)}。`
              : ""}
          </p>
        </div>
        <WorkbenchStatusPill
          status={finalAttempt.status}
          tone={finalAttempt.status === "succeeded" ? "green" : "red"}
        >
          {finalAttempt.status === "succeeded" ? "步骤完成" : "步骤未完成"}
        </WorkbenchStatusPill>
      </div>
      <details className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
          查看尝试诊断
        </summary>
        <ol className="mt-3 grid gap-2">
          {attempts.map((attempt) => (
            <li
              className="rounded-[var(--radius-2)] bg-[var(--surface-muted)] p-2"
              key={attempt.id}
            >
              <p className="font-semibold text-[var(--text-primary)]">
                第 {attempt.attemptNumber} 次 ·{" "}
                {attemptStatusLabel(attempt.status)}
              </p>
              <p className="mt-1 break-all">
                code: {attempt.errorCode ?? "none"} · backoff:{" "}
                {attempt.backoffMs}ms
              </p>
              <p className="mt-1 break-all">
                attempt key: {attempt.attemptKeyHash}
              </p>
            </li>
          ))}
        </ol>
        <p className="mt-3 font-semibold text-[var(--state-success)]">
          Provider call: false · Credential read: false · Production write:
          false
        </p>
      </details>
    </article>
  );
}

function FallbackDecisionEvidenceCard({
  decision,
}: {
  decision: WorkflowFallbackDecisionEvidence;
}) {
  const blockedGates = decision.gates.filter(
    (gate) => gate.status === "blocked",
  );
  return (
    <article className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="break-all text-sm font-semibold text-[var(--text-primary)]">
            {decision.stepRef}
          </p>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            {decision.outcome === "blocked"
              ? `备用路线未切换；${blockedGates.length} 项门禁未通过。`
              : "全部门禁通过，可进入人工治理复核；当前仍未切换路线。"}
          </p>
        </div>
        <WorkbenchStatusPill
          status={decision.outcome}
          tone={decision.outcome === "blocked" ? "amber" : "green"}
        >
          {decision.outcome === "blocked" ? "切换已阻止" : "等待人工复核"}
        </WorkbenchStatusPill>
      </div>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        <StateFact
          label="主路线失败"
          value={attemptErrorLabel(decision.primaryFailureCode)}
        />
        <StateFact
          label="人工审批"
          value={fallbackApprovalLabel(decision.approvalStatus)}
        />
      </dl>
      {decision.fieldDifference.missingRequiredFields.length > 0 ? (
        <p className="mt-3 text-xs leading-5 text-[var(--state-danger)]">
          备用路线缺失必填字段：
          {decision.fieldDifference.missingRequiredFields.join("、")}
        </p>
      ) : null}
      <details className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
          查看 Fallback 诊断
        </summary>
        <dl className="mt-3 grid gap-2">
          <ShadowDiagnosticFact
            label="主路线"
            value={decision.primaryImplementationId}
          />
          <ShadowDiagnosticFact
            label="备用路线"
            value={decision.fallbackImplementationId ?? "unavailable"}
          />
          <ShadowDiagnosticFact
            label="阻止门禁"
            value={
              blockedGates.length > 0
                ? blockedGates
                    .map((gate) => `${gate.gate}: ${gate.code}`)
                    .join("、")
                : "none"
            }
          />
          <ShadowDiagnosticFact
            label="决策摘要"
            value={decision.decisionDigest}
          />
          <ShadowDiagnosticFact
            label="成本证据"
            value={`${decision.costSnapshot.unitCostUsd ?? "unknown"} / ${decision.costSnapshot.ceilingUsd ?? "not set"} USD`}
          />
          <ShadowDiagnosticFact
            label="证据引用"
            value={decision.evidenceRefs.join("、") || "none"}
          />
        </dl>
        <p className="mt-3 font-semibold text-[var(--state-success)]">
          Switch executed: false · Provider call: false · Production write:
          false
        </p>
      </details>
    </article>
  );
}

function CheckpointBudgetEvidencePanel({
  result,
}: {
  result: WorkflowCheckpointBudgetEvidence;
}) {
  const confirmedRecords = result.checkpointSteps.reduce(
    (total, step) => total + step.confirmedRecords,
    0,
  );
  return (
    <section
      aria-labelledby="workflow-checkpoint-budget-heading"
      className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4"
      data-testid="workflow-checkpoint-budget-evidence"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-[var(--accent-primary)]">
          <BookmarkCheck aria-hidden="true" size={18} />
        </span>
        <div className="min-w-0 flex-1">
          <h3
            className="text-sm font-semibold text-[var(--text-primary)]"
            id="workflow-checkpoint-budget-heading"
          >
            断点与预算
          </h3>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            读取已确认分页与五维预算账本；本区不提供恢复执行或覆盖预算操作。
          </p>
        </div>
        <WorkbenchStatusPill
          status={result.budgetStatus}
          tone={result.budgetStatus === "held" ? "amber" : "green"}
        >
          {budgetStatusLabel(result.budgetStatus)}
        </WorkbenchStatusPill>
      </div>

      <dl className="mt-4 grid gap-2 sm:grid-cols-3">
        <StateFact
          label="已确认分页"
          value={`${result.checkpointPageTotal} 页`}
        />
        <StateFact label="已保存记录" value={`${confirmedRecords} 条`} />
        <StateFact label="预算账本" value={`${result.budgetEntryTotal} 条`} />
      </dl>

      {result.budgetStatus === "held" ? (
        <div
          className="mt-4 rounded-[var(--radius-2)] border border-[var(--state-warning)] bg-[var(--warning-soft)] p-3"
          role="status"
        >
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            预算已暂停
          </p>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            {budgetBlockerLabel(result.heldReasonCode)}
            。已确认断点仍保持只读；需在治理流程中处理预算后再评估是否恢复。
          </p>
        </div>
      ) : null}

      <div className="mt-4 border-t border-[var(--border-subtle)] pt-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <BookmarkCheck aria-hidden="true" size={15} />
          分页断点
        </div>
        {result.checkpointSteps.length === 0 ? (
          <EvidenceEmptyState>
            当前 Run
            没有已配置或已读取的断点证据；这不代表可以安全恢复，也不会自动补跑。
          </EvidenceEmptyState>
        ) : (
          <div className="mt-3 grid gap-3">
            {result.checkpointSteps.map((step) => (
              <CheckpointEvidenceCard key={step.stepRunId} step={step} />
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 border-t border-[var(--border-subtle)] pt-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
          <Gauge aria-hidden="true" size={15} />
          五维预算
        </div>
        {result.budgetAccount === null || result.usage === null ? (
          <EvidenceEmptyState>
            当前 Run
            没有已配置或已读取的预算账户证据；这不代表预算无限，也不授权任何外部调用。
          </EvidenceEmptyState>
        ) : (
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <BudgetMetric
              label="请求次数"
              limit={result.usage.requestLimit}
              unit="次"
              used={result.usage.requestCount}
            />
            <BudgetMetric
              label="数据条目"
              limit={result.usage.itemLimit}
              unit="条"
              used={result.usage.itemCount}
            />
            <BudgetMetric
              label="预估成本"
              limit={Number(result.usage.costLimitUsd)}
              unit="USD"
              used={Number(result.usage.costUsd)}
            />
            <BudgetMetric
              label="预留时长"
              limit={result.usage.timeLimitMs}
              unit="ms"
              used={result.usage.timeMs}
            />
            {Object.entries(result.usage.quotaCeilings).map(([key, limit]) => (
              <BudgetMetric
                key={key}
                label={`Quota · ${key}`}
                limit={limit}
                unit="units"
                used={result.usage?.quotaUnits[key] ?? 0}
              />
            ))}
          </div>
        )}
      </div>

      <details className="mt-4 border-t border-[var(--border-subtle)] pt-3 text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
          查看断点与账本诊断
        </summary>
        <dl className="mt-3 grid gap-2">
          <ShadowDiagnosticFact
            label="Execution session"
            value={result.executionSessionId}
          />
          <ShadowDiagnosticFact
            label="Policy digest"
            value={result.budgetAccount?.policyDigest ?? "not configured"}
          />
          <ShadowDiagnosticFact
            label="Final ledger digest"
            value={result.budgetEntries.at(-1)?.ledgerDigest ?? "none"}
          />
          <ShadowDiagnosticFact
            label="Next cursor"
            value={
              result.checkpointSteps.at(-1)?.nextCursor ?? "terminal / none"
            }
          />
        </dl>
        <p className="mt-3 font-semibold text-[var(--state-success)]">
          Resume action: false · Budget override: false · Provider call: false
        </p>
      </details>
    </section>
  );
}

function ProviderHealthEvidencePanel({
  result,
}: {
  result: WorkflowProviderHealthEvidence;
}) {
  const summaryStatus =
    result.observedCandidateTotal === 0
      ? "not_observed"
      : result.attentionCandidateTotal > 0
        ? "needs_attention"
        : "observed";
  return (
    <section
      aria-labelledby="workflow-provider-health-heading"
      className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4"
      data-testid="workflow-provider-health-evidence"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-[var(--state-info)]">
          <Activity aria-hidden="true" size={18} />
        </span>
        <div className="min-w-0 flex-1">
          <h3
            className="text-sm font-semibold text-[var(--text-primary)]"
            id="workflow-provider-health-heading"
          >
            Provider 健康证据
          </h3>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            汇总已提供的结构化观测；不会主动探测 Provider，也不会修改当前 Run
            的路线。
          </p>
        </div>
        <WorkbenchStatusPill
          status={summaryStatus}
          tone={
            result.observedCandidateTotal === 0
              ? "neutral"
              : result.attentionCandidateTotal > 0
                ? "amber"
                : "green"
          }
        >
          {result.observedCandidateTotal === 0
            ? "未观测"
            : result.attentionCandidateTotal > 0
              ? "需要关注"
              : "已有观测"}
        </WorkbenchStatusPill>
      </div>

      <dl className="mt-4 grid gap-2 sm:grid-cols-3">
        <StateFact
          label="已观测候选"
          value={`${result.observedCandidateTotal} 个`}
        />
        <StateFact
          label="路由时效内"
          value={`${result.routingActiveCandidateTotal} 个`}
        />
        <StateFact label="路线反馈" value={`${result.routeFeedbackTotal} 条`} />
      </dl>

      {result.observedCandidateTotal === 0 ? (
        <EvidenceEmptyState>
          当前 Run 没有可匹配的健康快照；这不代表 Provider
          健康，也不代表可以安全切换路线。
        </EvidenceEmptyState>
      ) : (
        <div className="mt-4 grid gap-3">
          {result.steps.map((step) => (
            <article
              className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3"
              key={step.stepRunId}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="break-all text-sm font-semibold text-[var(--text-primary)]">
                    {step.stepRef}
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    {step.platformId} / {step.resourceType} / {step.operation}
                  </p>
                </div>
                <span className="text-xs font-semibold text-[var(--text-tertiary)]">
                  {step.candidates.length} 个候选
                </span>
              </div>

              <div className="mt-3 divide-y divide-[var(--border-subtle)] rounded-[var(--radius-2)] border border-[var(--border-subtle)]">
                {step.candidates.map((candidate) => (
                  <div
                    className="grid gap-2 px-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                    key={candidate.implementationId}
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="break-all text-xs font-semibold text-[var(--text-primary)]">
                          {candidate.implementationId}
                        </p>
                        {candidate.selectedForRun ? (
                          <span className="rounded-[var(--radius-1)] bg-[var(--accent-1-soft)] px-2 py-0.5 text-xs font-semibold text-[var(--action-primary)]">
                            本 Run 已选
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                        {candidate.snapshot
                          ? `成功率 ${(candidate.snapshot.successRateBps / 100).toFixed(2)}% · P95 ${candidate.snapshot.p95LatencyMs}ms · ${providerHealthRoutingLabel(candidate.routingState)}`
                          : "没有匹配快照，不能推断健康状态或路由可用性。"}
                      </p>
                    </div>
                    <WorkbenchStatusPill
                      status={candidate.healthStatus}
                      tone={providerHealthTone(candidate.healthStatus)}
                    >
                      {providerHealthStatusLabel(candidate.healthStatus)}
                    </WorkbenchStatusPill>
                  </div>
                ))}
              </div>

              {step.routeFeedback ? (
                <div className="mt-3 rounded-[var(--radius-2)] bg-[var(--surface-muted)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
                  <p className="font-semibold text-[var(--text-primary)]">
                    {step.routeFeedback.rankingChanged
                      ? "观测反馈建议调整候选顺序"
                      : "观测反馈保持候选顺序"}
                  </p>
                  <p className="mt-1 break-words">
                    {step.routeFeedback.originalCandidateOrder.join(" → ")} →{" "}
                    {step.routeFeedback.adjustedCandidateOrder.join(" → ")}
                  </p>
                  <p className="mt-1 font-semibold text-[var(--state-warning)]">
                    只读建议，未应用到此 Run。
                  </p>
                </div>
              ) : (
                <p className="mt-3 text-xs leading-5 text-[var(--text-secondary)]">
                  没有候选顺序精确匹配的路线反馈；不据此判断路线优先级。
                </p>
              )}
            </article>
          ))}
        </div>
      )}

      <details className="mt-4 border-t border-[var(--border-subtle)] pt-3 text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
          查看 Provider Health 诊断
        </summary>
        <dl className="mt-3 grid gap-2">
          <ShadowDiagnosticFact label="Read at" value={result.readAt} />
          <ShadowDiagnosticFact
            label="Snapshot digests"
            value={
              result.steps
                .flatMap((step) => step.candidates)
                .flatMap((candidate) =>
                  candidate.snapshot ? [candidate.snapshot.snapshotDigest] : [],
                )
                .join("、") || "none"
            }
          />
          <ShadowDiagnosticFact
            label="Feedback digests"
            value={
              result.steps
                .flatMap((step) =>
                  step.routeFeedback ? [step.routeFeedback.feedbackDigest] : [],
                )
                .join("、") || "none"
            }
          />
        </dl>
        <p className="mt-3 font-semibold text-[var(--state-success)]">
          Health probe: false · Catalog mutation: false · Automatic switch:
          false · Provider call: false
        </p>
      </details>
    </section>
  );
}

function EvidenceEmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 rounded-[var(--radius-2)] border border-dashed border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-4 text-sm leading-6 text-[var(--text-secondary)]">
      {children}
    </p>
  );
}

function CheckpointEvidenceCard({
  step,
}: {
  step: WorkflowCheckpointStepEvidence;
}) {
  return (
    <article className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="break-all text-sm font-semibold text-[var(--text-primary)]">
            {step.stepRef}
          </p>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            已确认 {step.confirmedPages} 页、保存 {step.confirmedRecords}{" "}
            条记录；
            {step.terminal
              ? "分页已完成。"
              : `停在第 ${step.nextPageNumber} 页之前。`}
          </p>
        </div>
        <WorkbenchStatusPill
          status={step.terminal ? "terminal" : "checkpointed"}
          tone={step.terminal ? "green" : "amber"}
        >
          {step.terminal ? "分页完成" : "保留断点"}
        </WorkbenchStatusPill>
      </div>
      <details className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
          查看分页诊断
        </summary>
        <ol className="mt-3 grid gap-2">
          {step.checkpoints.map((checkpoint) => (
            <li
              className="rounded-[var(--radius-2)] bg-[var(--surface-muted)] p-2"
              key={checkpoint.id}
            >
              <p className="font-semibold text-[var(--text-primary)]">
                第 {checkpoint.pageNumber} 页 · {checkpoint.recordsCount} 条
              </p>
              <p className="mt-1 break-all">
                checkpoint: {checkpoint.checkpointDigest}
              </p>
              <p className="mt-1 break-all">
                evidence: {checkpoint.evidenceRefs.join("、")}
              </p>
            </li>
          ))}
        </ol>
      </details>
    </article>
  );
}

function BudgetMetric({
  label,
  limit,
  unit,
  used,
}: {
  label: string;
  limit: number;
  unit: string;
  used: number;
}) {
  const percent =
    limit > 0 ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0;
  return (
    <div className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-semibold text-[var(--text-primary)]">
          {label}
        </span>
        <span className="text-[var(--text-secondary)]">
          {used} / {limit} {unit}
        </span>
      </div>
      <div
        aria-label={`${label} 已使用 ${percent.toFixed(0)}%`}
        className="mt-2 h-2 overflow-hidden rounded-[var(--radius-pill)] bg-[var(--surface-muted)]"
        role="progressbar"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={Math.round(percent)}
      >
        <div
          className="h-full rounded-[var(--radius-pill)] bg-[var(--accent-primary)]"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function ShadowComparisonPanel({
  result,
}: {
  result: WorkflowShadowComparisonListResult;
}) {
  return (
    <section
      aria-labelledby="workflow-shadow-comparison-heading"
      className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4"
      data-testid="workflow-shadow-comparisons"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-[var(--accent-primary)]">
          <GitCompareArrows aria-hidden="true" size={18} />
        </span>
        <div className="min-w-0">
          <h3
            className="text-sm font-semibold text-[var(--text-primary)]"
            id="workflow-shadow-comparison-heading"
          >
            路线对比（Shadow）
          </h3>
          <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
            读取冻结 fixture 的主路线与 Shadow
            路线差异；推荐只供治理复核，不会自动修改 Catalog、切换路线或调用
            Provider。
          </p>
        </div>
      </div>

      {result.items.length === 0 ? (
        <p className="mt-4 rounded-[var(--radius-2)] border border-dashed border-[var(--border-default)] bg-[var(--surface-primary)] px-3 py-4 text-sm text-[var(--text-secondary)]">
          当前 Run 没有 Shadow 对比证据；这不代表路线等价，也不会触发自动补跑。
        </p>
      ) : (
        <div className="mt-4 grid gap-3">
          {result.items.map((comparison) => (
            <ShadowComparisonCard comparison={comparison} key={comparison.id} />
          ))}
        </div>
      )}
    </section>
  );
}

function ShadowComparisonCard({
  comparison,
}: {
  comparison: WorkflowShadowComparison;
}) {
  const differenceCount =
    comparison.mismatchedItems +
    comparison.primaryOnlyItems +
    comparison.shadowOnlyItems;
  return (
    <article className="rounded-[var(--radius-2)] border border-[var(--border-default)] bg-[var(--surface-primary)] p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="break-all text-sm font-semibold text-[var(--text-primary)]">
            {comparison.requirementRef}
          </p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            {comparison.sampledItems} 条样本 · {comparison.matchedItems} 条一致
            · {differenceCount} 条差异
          </p>
        </div>
        <WorkbenchStatusPill
          status={comparison.equivalenceStatus}
          tone={
            comparison.equivalenceStatus === "equivalent" ? "green" : "amber"
          }
        >
          {comparison.equivalenceStatus === "equivalent"
            ? "样本等价"
            : "发现差异"}
        </WorkbenchStatusPill>
      </div>

      <div className="mt-3 rounded-[var(--radius-2)] bg-[var(--surface-tertiary)] p-3">
        <p className="text-xs font-semibold text-[var(--text-tertiary)]">
          治理建议
        </p>
        <p className="mt-1 text-sm font-semibold leading-5 text-[var(--text-primary)]">
          {shadowRecommendationLabel(comparison.routingRecommendation)}
        </p>
        {comparison.differenceEvidence.missingRequiredFields.length > 0 ? (
          <p className="mt-2 text-xs leading-5 text-[var(--state-danger)]">
            缺失必填字段：
            {comparison.differenceEvidence.missingRequiredFields.join("、")}
          </p>
        ) : null}
      </div>

      <details className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">
          查看诊断证据
        </summary>
        <dl className="mt-3 grid gap-2">
          <ShadowDiagnosticFact
            label="主路线"
            value={comparison.primaryImplementationId}
          />
          <ShadowDiagnosticFact
            label="Shadow 路线"
            value={comparison.shadowImplementationId}
          />
          <ShadowDiagnosticFact
            label="对比摘要"
            value={comparison.comparisonDigest}
          />
          <ShadowDiagnosticFact
            label="证据引用"
            value={comparison.evidenceRefs.join("、")}
          />
        </dl>
        <p className="mt-3 font-semibold text-[var(--state-success)]">
          Catalog mutation: false · Route ranking mutation: false
        </p>
      </details>
    </article>
  );
}

function ShadowDiagnosticFact({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[7rem_minmax(0,1fr)]">
      <dt className="font-semibold text-[var(--text-tertiary)]">{label}</dt>
      <dd className="break-all">{value}</dd>
    </div>
  );
}

function StateFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-2)] bg-[var(--surface-primary)] p-3">
      <dt className="text-xs font-semibold text-[var(--text-tertiary)]">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-semibold leading-5 text-[var(--text-primary)]">
        {value}
      </dd>
    </div>
  );
}

function BoundaryFact({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Database;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-[#E8DDD6] bg-[#FBF8F5] p-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#9A7467]">
        <Icon aria-hidden="true" size={13} />
        {label}
      </div>
      <p className="mt-1 text-sm font-semibold text-[#3B2924]">{value}</p>
    </div>
  );
}

function LineageFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[#E8DDD6] bg-white/70 p-2">
      <p className="font-semibold uppercase text-[#9A7467]">{label}</p>
      <p className="mt-1 font-semibold text-[#3B2924]">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: WorkflowRunStatus }) {
  const tone =
    status === "completed" || status === "empty_valid"
      ? "green"
      : status === "held" || status === "degraded" || status === "running"
        ? "amber"
        : status === "cancelled"
          ? "red"
          : "neutral";
  return (
    <WorkbenchStatusPill status={status} tone={tone}>
      {statusLabel(status)}
    </WorkbenchStatusPill>
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

function assertListResponse(
  result: WorkflowRunListResult,
  projectId: string,
  offset: number,
): void {
  const boundaryMismatch =
    result.projectStatus !== "active" ||
    result.executionMode !== "fixture" ||
    result.liveExecutionAuthorized ||
    result.providerCall ||
    result.providerCallAttempted ||
    result.credentialReadAttempted ||
    result.actorRun ||
    result.browserRun ||
    result.llmCall ||
    result.rawRecordWrite ||
    result.datasetWrite ||
    result.productionWriteAllowed ||
    result.databaseWrite;
  const paginationMismatch =
    result.limit !== PAGE_LIMIT ||
    result.offset !== offset ||
    !Number.isInteger(result.total) ||
    result.total < 0 ||
    result.items.length > PAGE_LIMIT ||
    result.total < result.offset + result.items.length ||
    (result.items.length === 0 && result.offset < result.total);
  const projectMismatch = result.items.some(
    (item) => item.projectId !== projectId,
  );

  if (boundaryMismatch || paginationMismatch || projectMismatch) {
    throw new Error("workflow_run_list_response_context_mismatch");
  }
}

function assertDetailResponse(
  result: WorkflowRunDetail,
  projectId: string,
  runId: string,
): void {
  const boundaryMismatch =
    result.projectStatus !== "active" ||
    result.executionMode !== "fixture" ||
    result.liveExecutionAuthorized ||
    result.providerCall ||
    result.providerCallAttempted ||
    result.credentialReadAttempted ||
    result.actorRun ||
    result.browserRun ||
    result.llmCall ||
    result.rawRecordWrite ||
    result.datasetWrite ||
    result.productionWriteAllowed ||
    result.databaseWrite;
  const ownershipMismatch =
    result.run.id !== runId ||
    result.run.projectId !== projectId ||
    result.steps.some(
      (step) => step.projectId !== projectId || step.workflowRunId !== runId,
    );

  if (boundaryMismatch || ownershipMismatch) {
    throw new Error("workflow_run_detail_response_context_mismatch");
  }
}

function assertAttemptFallbackEvidenceResponse(
  result: WorkflowAttemptFallbackEvidence,
  detail: WorkflowRunDetail,
  projectId: string,
  runId: string,
): void {
  const stepIds = new Set(detail.steps.map((step) => step.id));
  const boundaryMismatch =
    result.schemaVersion !== "workflow_attempt_fallback_evidence.v1" ||
    result.executionMode !== "fixture" ||
    result.liveExecutionAuthorized ||
    result.providerCall ||
    result.providerCallAttempted ||
    result.credentialReadAttempted ||
    result.actorRun ||
    result.browserRun ||
    result.llmCall ||
    result.rawRecordWrite ||
    result.datasetWrite ||
    result.productionWriteAllowed ||
    result.databaseWrite;
  const ownershipMismatch =
    result.projectId !== projectId ||
    result.workflowRunId !== runId ||
    result.attemptTotal !== result.attempts.length ||
    result.fallbackDecisionTotal !== result.fallbackDecisions.length ||
    result.attempts.some((item) => !stepIds.has(item.stepRunId)) ||
    result.fallbackDecisions.some(
      (item) =>
        !stepIds.has(item.stepRunId) ||
        item.workflowPlanId !== detail.run.workflowPlanId ||
        item.workflowVersionId !== detail.run.workflowVersionId,
    );
  if (boundaryMismatch || ownershipMismatch) {
    throw new Error("workflow_attempt_fallback_response_context_mismatch");
  }
}

function assertCheckpointBudgetEvidenceResponse(
  result: WorkflowCheckpointBudgetEvidence,
  detail: WorkflowRunDetail,
  projectId: string,
  runId: string,
): void {
  const stepIds = new Set(detail.steps.map((step) => step.id));
  const boundaryMismatch =
    result.schemaVersion !== "workflow_checkpoint_budget_evidence.v1" ||
    result.executionMode !== "fixture" ||
    result.liveExecutionAuthorized ||
    result.providerCall ||
    result.providerCallAttempted ||
    result.credentialReadAttempted ||
    result.actorRun ||
    result.browserRun ||
    result.llmCall ||
    result.rawRecordWrite ||
    result.datasetWrite ||
    result.productionWriteAllowed ||
    result.databaseWrite ||
    result.resumeActionAvailable ||
    result.budgetOverrideAvailable;
  const ownershipMismatch =
    result.projectId !== projectId ||
    result.workflowRunId !== runId ||
    result.executionSessionId !== runId ||
    result.workflowPlanId !== detail.run.workflowPlanId ||
    result.workflowVersionId !== detail.run.workflowVersionId ||
    result.checkpointStepTotal !== result.checkpointSteps.length ||
    result.budgetEntryTotal !== result.budgetEntries.length ||
    result.checkpointSteps.some(
      (step) =>
        !stepIds.has(step.stepRunId) ||
        step.executionSessionId !== runId ||
        step.resumeActionAvailable,
    ) ||
    (result.budgetAccount !== null &&
      (result.budgetAccount.executionSessionId !== runId ||
        result.budgetAccount.workflowPlanId !== detail.run.workflowPlanId ||
        result.budgetAccount.workflowVersionId !==
          detail.run.workflowVersionId));
  if (boundaryMismatch || ownershipMismatch) {
    throw new Error("workflow_checkpoint_budget_response_context_mismatch");
  }
}

function assertProviderHealthEvidenceResponse(
  result: WorkflowProviderHealthEvidence,
  detail: WorkflowRunDetail,
  projectId: string,
  runId: string,
): void {
  const steps = new Map(detail.steps.map((step) => [step.id, step]));
  const boundaryMismatch =
    result.schemaVersion !== "workflow_provider_health_evidence.v1" ||
    result.executionMode !== "fixture" ||
    result.liveExecutionAuthorized ||
    result.providerCall ||
    result.providerCallAttempted ||
    result.credentialReadAttempted ||
    result.actorRun ||
    result.browserRun ||
    result.llmCall ||
    result.rawRecordWrite ||
    result.datasetWrite ||
    result.productionWriteAllowed ||
    result.databaseWrite ||
    result.healthProbeAttempted ||
    result.catalogMutationApplied ||
    result.automaticRouteSwitchExecuted ||
    result.routeSwitchActionAvailable;
  const ownershipMismatch =
    result.workspaceId !== detail.run.workspaceId ||
    result.projectId !== projectId ||
    result.workflowRunId !== runId ||
    result.stepTotal !== detail.steps.length ||
    result.steps.some((item) => {
      const step = steps.get(item.stepRunId);
      return (
        step === undefined ||
        item.stepRef !== step.stepRef ||
        item.requirementRef !== step.requirementRef ||
        item.platformId !== step.platform ||
        item.resourceType !== step.resourceType ||
        item.operation !== step.operation ||
        item.selectedImplementationId !== step.implementationId ||
        item.routeDecisionAppliedToRun
      );
    });
  if (boundaryMismatch || ownershipMismatch) {
    throw new Error("workflow_provider_health_response_context_mismatch");
  }
}

function assertExecutorEvidenceResponse(
  evidence: WorkflowExecutorEvidence,
  detail: WorkflowRunDetail,
  projectId: string,
  runId: string,
): void {
  const stepIds = new Set(detail.steps.map((step) => step.id));
  if (
    evidence.projectId !== projectId ||
    evidence.workflowRunId !== runId ||
    evidence.workspaceId !== detail.run.workspaceId ||
    evidence.executionMode !== "fixture" ||
    evidence.evidenceGrade !== "L2_fixture_local" ||
    evidence.liveExecutionAuthorized ||
    evidence.credentialReadAttempted ||
    evidence.clientConstruction ||
    evidence.providerCall ||
    evidence.providerCallAttempted ||
    evidence.networkCall ||
    evidence.liveProviderProof ||
    evidence.databaseWrite ||
    evidence.dispatches.some(
      (dispatch) => !stepIds.has(dispatch.workflowStepRunId),
    )
  ) {
    throw new Error("workflow_executor_evidence_response_mismatch");
  }
}

function assertActionGatesResponse(
  result: WorkflowRunActionGates,
  detail: WorkflowRunDetail,
  projectId: string,
  runId: string,
): void {
  const sharedBoundaryMismatch =
    result.executionMode !== "fixture" ||
    result.liveExecutionAuthorized ||
    result.providerCall ||
    result.providerCallAttempted ||
    result.credentialReadAttempted ||
    result.actorRun ||
    result.browserRun ||
    result.llmCall ||
    result.rawRecordWrite ||
    result.datasetWrite ||
    result.productionWriteAllowed ||
    result.databaseWrite ||
    result.actionMutationExecuted;
  const contractMismatch =
    result.schemaVersion === "workflow_run_action_gates.v1"
      ? result.availableActionTotal !== 0 ||
        result.mutationEndpointsAvailable ||
        result.durableActionAuditAvailable ||
        result.gates.some((item) => item.actionAvailable)
      : !result.mutationEndpointsAvailable ||
        !result.durableActionAuditAvailable ||
        result.availableActionTotal !==
          result.gates.filter((item) => item.submissionAvailable).length;
  const ownershipMismatch =
    result.workspaceId !== detail.run.workspaceId ||
    result.projectId !== projectId ||
    result.workflowPlanId !== detail.run.workflowPlanId ||
    result.workflowVersionId !== detail.run.workflowVersionId ||
    result.workflowRunId !== runId ||
    result.runStatus !== detail.run.status;
  if (sharedBoundaryMismatch || contractMismatch || ownershipMismatch) {
    throw new Error("workflow_run_action_gates_response_context_mismatch");
  }
}

function assertLineagePreviewResponse(
  result: WorkflowRunLineagePreview,
  projectId: string,
  runId: string,
): void {
  const boundaryMismatch =
    result.executionMode !== "fixture" ||
    result.liveExecutionAuthorized ||
    result.providerCall ||
    result.providerCallAttempted ||
    result.credentialReadAttempted ||
    result.actorRun ||
    result.browserRun ||
    result.llmCall ||
    result.rawRecordWrite ||
    result.datasetWrite ||
    result.productionWriteAllowed ||
    result.databaseWrite ||
    result.rawRecord.rawRecordWrite ||
    result.dataset.datasetWrite;
  const providerStepIds = result.providerEvidence.map((item) => item.stepRunId);
  const ownershipMismatch =
    result.workflowRunId !== runId ||
    result.projectId !== projectId ||
    providerStepIds.length === 0 ||
    new Set(providerStepIds).size !== providerStepIds.length ||
    providerStepIds.join("|") !== result.rawRecord.sourceStepRunIds.join("|") ||
    providerStepIds.join("|") !== result.dataset.sourceStepRunIds.join("|");

  if (boundaryMismatch || ownershipMismatch) {
    throw new Error("workflow_lineage_preview_response_context_mismatch");
  }
}

function assertShadowComparisonResponse(
  result: WorkflowShadowComparisonListResult,
  projectId: string,
  runId: string,
): void {
  const boundaryMismatch =
    result.executionMode !== "fixture" ||
    result.liveExecutionAuthorized ||
    result.providerCall ||
    result.providerCallAttempted ||
    result.credentialReadAttempted ||
    result.actorRun ||
    result.browserRun ||
    result.llmCall ||
    result.rawRecordWrite ||
    result.datasetWrite ||
    result.productionWriteAllowed ||
    result.databaseWrite;
  const ownershipMismatch =
    result.total !== result.items.length ||
    result.items.some(
      (item) =>
        item.projectId !== projectId ||
        item.workflowRunId !== runId ||
        item.catalogMutationApplied ||
        item.routeRankingMutationApplied,
    );
  if (boundaryMismatch || ownershipMismatch) {
    throw new Error("workflow_shadow_comparison_response_context_mismatch");
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function errorMessage(error: unknown): string {
  return error instanceof Error && error.message.trim()
    ? error.message
    : "WorkflowRun 暂不可用";
}

function formatTimestamp(value: string | null): string {
  if (value === null) {
    return "尚未结束";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", { hour12: false });
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

function nextWorkflowActionIdempotencyKey(
  scope: "action" | "approval",
): string {
  const nonce =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `workflow-${scope}-${nonce}`;
}

function statusLabel(status: WorkflowRunStatus): string {
  const labels: Record<WorkflowRunStatus, string> = {
    draft: "草稿",
    ready: "就绪",
    running: "运行中",
    completed: "已完成",
    degraded: "降级",
    held: "已暂停，等待处理",
    cancelled: "已取消",
    empty_valid: "有效空结果",
  };
  return labels[status];
}

function runActionLabel(action: WorkflowRunAction): string {
  return {
    retry: "重试失败步骤",
    resume: "从检查点恢复",
    cancel: "取消当前运行",
    budget_override: "申请预算覆盖",
    route_switch: "评审路线切换",
  }[action];
}

function runActionPreconditionLabel(
  status: WorkflowRunActionPreconditionStatus,
): string {
  return {
    ready_for_review: "条件可评审",
    blocked: "已阻断",
    not_applicable: "当前不适用",
  }[status];
}

function runActionBlockerLabel(
  code: WorkflowRunActionPreconditionBlockerCode,
): string {
  const labels: Record<WorkflowRunActionPreconditionBlockerCode, string> = {
    run_state_not_retryable: "当前运行状态不支持重试评估",
    failed_step_unavailable: "没有可定位的失败步骤",
    retry_evidence_unavailable: "缺少连续的尝试证据",
    terminal_failure_not_retryable: "最新失败为不可重试错误",
    retry_policy_snapshot_unavailable: "缺少冻结的重试策略快照",
    run_state_not_resumable: "当前运行状态不支持恢复评估",
    resume_checkpoint_unavailable: "没有已确认的恢复断点",
    resume_checkpoint_terminal: "断点链已终止，无法继续分页",
    budget_account_unavailable: "缺少可核验的预算账户",
    budget_limit_exceeded: "预算账本已达到限制",
    run_state_not_cancellable: "当前运行状态无需或不能取消",
    budget_not_held: "当前运行不是预算暂停状态",
    owner_approval_receipt_unavailable: "缺少 Owner 审批凭证",
    run_state_not_switchable: "当前运行状态不支持路线切换评估",
    fallback_decision_unavailable: "缺少失败步骤的回退决策",
    fallback_gate_blocked: "至少一个回退证据门仍被阻断",
    route_feedback_unavailable: "缺少与候选顺序匹配的路线反馈",
  };
  return labels[code];
}

function runActionNextLabel(code: WorkflowRunActionNextActionCode): string {
  return {
    no_action_required: "无需动作，保留只读证据",
    inspect_retry_evidence: "检查失败尝试与重试策略证据",
    restore_checkpoint_budget: "补齐断点与预算前置条件",
    review_resume_request: "提交恢复请求进行人工评审",
    review_cancel_request: "提交取消请求进行人工评审",
    request_budget_override_approval: "申请预算覆盖的 Owner 审批",
    resolve_fallback_gates: "处理回退门禁与路线反馈",
    review_route_switch: "提交路线切换请求进行人工评审",
  }[code];
}

function stepStatusLabel(
  status: "pending" | "running" | "completed" | "failed" | "cancelled",
): string {
  return {
    pending: "等待中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  }[status];
}

function reasonLabel(code: string): string {
  return (
    {
      fallback_blocked: "主路径失败，Fallback 证据门未允许切换",
      verified_zero_result: "所有步骤已成功完成，并验证结果数为 0",
    }[code] ?? code
  );
}

function impactLabel(code: string): string {
  return (
    {
      step_not_completed_following_steps_not_started:
        "当前步骤未完成，后续步骤尚未启动",
      no_records_in_scope: "本次范围内没有可写入的记录",
    }[code] ?? code
  );
}

function executorCauseLabel(
  code: WorkflowExecutorEvidence["businessCauseCode"],
): string {
  return {
    executor_dispatch_not_created: "尚未创建执行器派发",
    executor_dispatch_pending: "派发已记录，执行尚未开始",
    executor_preflight_blocked: "执行器预检已阻断",
    executor_waiting_exact_live_authority: "预检可继续，但尚缺精确 Live Provider 授权",
  }[code];
}

function executorImpactLabel(
  code: WorkflowExecutorEvidence["businessImpactCode"],
): string {
  return {
    workflow_execution_not_started: "当前工作流未启动外部执行",
    workflow_execution_waiting: "当前工作流保持等待，不会产生外部副作用",
  }[code];
}

function executorNextActionLabel(
  code: WorkflowExecutorEvidence["nextActionCode"],
): string {
  return {
    review_action_receipt_and_dispatch_gate: "核对动作收据与 dispatch 门禁",
    wait_for_disabled_executor_evidence: "等待禁用执行器生成更多本地证据",
    resolve_preflight_blocker: "先解决预检阻断项",
    request_exact_live_provider_authorization: "另行申请精确 Live Provider 授权",
  }[code];
}

function recoveryActionLabel(code: string): string {
  return (
    {
      inspect_fallback_gate_evidence: "检查 Fallback 门证据",
      resolve_primary_failure: "解决主路径失败后重试",
    }[code] ?? code
  );
}

function attemptStatusLabel(
  status: WorkflowStepAttemptEvidence["status"],
): string {
  return {
    succeeded: "已完成",
    retryable_error: "可重试错误",
    timeout: "执行超时",
    terminal_error: "不可重试错误",
  }[status];
}

function attemptErrorLabel(code: string): string {
  return (
    {
      step_network_unavailable: "网络暂不可用",
      step_rate_limited: "触发频率限制",
      step_timeout: "执行超时",
      step_contract_invalid: "数据合同不满足",
      step_request_rejected: "请求被拒绝",
    }[code] ?? "已记录失败，诊断中保留规范错误码"
  );
}

function fallbackApprovalLabel(
  status: WorkflowFallbackDecisionEvidence["approvalStatus"],
): string {
  return {
    not_required: "无需审批",
    approved: "已批准",
    pending: "等待人工审批",
    rejected: "审批未通过",
    unavailable: "审批证据不可用",
  }[status];
}

function budgetStatusLabel(
  status: WorkflowCheckpointBudgetEvidence["budgetStatus"],
): string {
  return {
    not_configured: "预算未配置",
    configured: "预算已配置",
    within_limit: "预算范围内",
    held: "预算已暂停",
  }[status];
}

function budgetBlockerLabel(code: WorkflowBudgetBlockerCode | null): string {
  if (code === null) {
    return "预算暂停原因未提供";
  }
  return {
    workflow_request_budget_exceeded: "请求次数已达到上限",
    workflow_item_budget_exceeded: "数据条目已达到上限",
    workflow_quota_budget_exceeded: "平台配额已达到上限",
    workflow_cost_budget_exceeded: "预估成本已达到上限",
    workflow_time_budget_exceeded: "预留时长已达到上限",
  }[code];
}

function providerHealthStatusLabel(
  status: WorkflowProviderHealthStatus,
): string {
  const labels: Record<WorkflowProviderHealthStatus, string> = {
    not_observed: "未观测",
    unknown: "样本不足",
    healthy: "健康",
    degraded: "降级",
    unhealthy: "不健康",
  };
  return labels[status];
}

function providerHealthRoutingLabel(
  state: "not_observed" | "routing_active" | "routing_expired",
): string {
  const labels = {
    not_observed: "无路由证据",
    routing_active: "处于路由时效内",
    routing_expired: "路由影响已过期，仅保留审计证据",
  } as const;
  return labels[state];
}

function providerHealthTone(
  status: WorkflowProviderHealthStatus,
): "neutral" | "green" | "amber" | "red" {
  if (status === "healthy") {
    return "green";
  }
  if (status === "degraded" || status === "unknown") {
    return "amber";
  }
  if (status === "unhealthy") {
    return "red";
  }
  return "neutral";
}

function shadowRecommendationLabel(
  recommendation: WorkflowShadowComparison["routingRecommendation"],
): string {
  return {
    eligible_for_governance_review: "样本等价，可进入人工治理复核",
    keep_primary_investigate_shadow: "保留主路线，并调查 Shadow 差异",
  }[recommendation];
}
