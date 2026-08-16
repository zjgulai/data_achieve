"use client";

import React from "react";

import {
  buildPlannerLifecyclePresentation,
  type PlannerLifecycleActionKey,
} from "@/lib/workflow-planner-lifecycle";
import type { WorkflowPlanStatus } from "@/types/workflow-plan-persistence";
import type {
  WorkflowFixtureRunGateBlockerCode,
  WorkflowRunStatus,
} from "@/types/workflow-run";
import type {
  WorkflowPlannerMode,
  WorkflowPlanningStatus,
} from "@/types/workflow-planner";

type WorkflowPlanSavePanelProps = {
  approvalReasonCount: number;
  planName: string;
  planNameLocked: boolean;
  planStatus: WorkflowPlanStatus | null;
  mode: WorkflowPlannerMode;
  currentVersionNumber: number | null;
  sourceVersionId: string | null;
  planningStatus: WorkflowPlanningStatus;
  missingOptionalFields: string[];
  saving: boolean;
  canSave: boolean;
  message: string | null;
  error: string | null;
  retryable: boolean;
  hasUnsavedChanges: boolean;
  activeAction: PlannerLifecycleActionKey | null;
  lifecycleMessage: string | null;
  lifecycleError: string | null;
  runGate: {
    status: "idle" | "loading" | "ready" | "error";
    runnable: boolean;
    blockerCodes: WorkflowFixtureRunGateBlockerCode[];
  };
  runReceipt: {
    id: string;
    status: WorkflowRunStatus;
    totalSteps: number;
    recordsCount: number;
  } | null;
  onPlanNameChange: (name: string) => void;
  onSave: () => void;
  onApprove: () => void;
  onActivate: () => void;
  onRun: () => void;
  onRefreshGate: () => void;
};

export function WorkflowPlanSavePanel({
  approvalReasonCount,
  planName,
  planNameLocked,
  planStatus,
  mode,
  currentVersionNumber,
  sourceVersionId,
  planningStatus,
  missingOptionalFields,
  saving,
  canSave,
  message,
  error,
  retryable,
  hasUnsavedChanges,
  activeAction,
  lifecycleMessage,
  lifecycleError,
  runGate,
  runReceipt,
  onPlanNameChange,
  onSave,
  onApprove,
  onActivate,
  onRun,
  onRefreshGate,
}: WorkflowPlanSavePanelProps) {
  const trimmedNameLength = planName.trim().length;
  const invalidName =
    !planNameLocked && (trimmedNameLength < 1 || trimmedNameLength > 200);
  const lifecycle = buildPlannerLifecyclePresentation({
    activeAction,
    canSave,
    currentVersionNumber,
    hasSavedReceipt: Boolean(message),
    hasUnsavedChanges,
    planStatus,
    runCreated: runReceipt !== null,
    runGate,
    missingOptionalFields,
    planningStatus,
    saving,
  });
  const saveAction = lifecycle.actions.find((action) => action.key === "save");
  const gatedActions = lifecycle.actions.filter(
    (action) => action.key !== "save",
  );
  const saveAvailable = saveAction?.state === "available";
  const saveStateLabel =
    saveAction?.state === "complete"
      ? "已完成"
      : saveAction?.state === "progress"
        ? "处理中"
        : saveAvailable
          ? "当前可执行"
          : "需先完成";
  const actionHandlers: Record<Exclude<PlannerLifecycleActionKey, "save">, () => void> =
    {
      approve: onApprove,
      activate: onActivate,
      run: onRun,
    };
  const statusTone =
    planningStatus === "resolved"
      ? "bg-[var(--success-soft)] text-[var(--state-success)]"
      : "bg-[var(--warning-soft)] text-[var(--state-warning)]";

  return (
    <section
      aria-labelledby="workflow-plan-review-heading"
      className="min-w-0 rounded-[var(--radius-4)] border border-[var(--border-strong)] bg-[var(--surface-secondary)] p-5 shadow-sm sm:p-6"
      data-testid="workflow-plan-save-panel"
    >
      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--state-info)]">
            Step 5 · explicit lifecycle
          </p>
          <h3
            className="mt-1 text-xl font-semibold text-[var(--text-primary)]"
            id="workflow-plan-review-heading"
          >
            Review 与保存
          </h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
            先复核阻断与版本影响，再执行唯一可用的持久化动作。后续状态不会被保存动作隐式推进。
          </p>
        </div>
        <p className="shrink-0 rounded-[var(--radius-pill)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-1.5 text-sm font-semibold text-[var(--text-secondary)]">
          {mode === "periodic_monitoring" ? "周期监测" : "批量研究"}
          {currentVersionNumber === null
            ? " · 新 Plan"
            : ` · 当前基线 v${currentVersionNumber}`}
          {planStatus ? ` · ${planStatus}` : ""}
        </p>
      </div>

      <div className="mt-5 grid min-w-0 gap-3 lg:grid-cols-[minmax(0,1.35fr)_minmax(16rem,0.65fr)]">
        <section className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-semibold text-[var(--text-primary)]">
              阻断摘要
            </h4>
            <span
              className={`rounded-[var(--radius-pill)] px-2.5 py-1 text-xs font-semibold ${statusTone}`}
            >
              {lifecycle.statusLabel}
            </span>
          </div>
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="font-semibold text-[var(--text-tertiary)]">
                原因
              </dt>
              <dd className="mt-1 leading-6 text-[var(--text-primary)]">
                {lifecycle.cause}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-[var(--text-tertiary)]">
                影响
              </dt>
              <dd className="mt-1 leading-6 text-[var(--text-primary)]">
                {lifecycle.impact}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-[var(--text-tertiary)]">
                下一步
              </dt>
              <dd className="mt-1 leading-6 text-[var(--text-primary)]">
                {lifecycle.nextAction}
              </dd>
            </div>
          </dl>
          <div className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-sm text-[var(--text-secondary)]">
            <p className="font-semibold text-[var(--text-primary)]">
              {approvalReasonCount} 条路线原因仍需处理
            </p>
            {lifecycle.missingFields.length > 0 ? (
              <p className="mt-1 break-words">
                缺失字段：{lifecycle.missingFields.join("、")}
              </p>
            ) : (
              <p className="mt-1">当前 Preview 未报告缺失字段。</p>
            )}
          </div>
        </section>

        <section className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-4">
          <h4 className="font-semibold text-[var(--text-primary)]">版本影响</h4>
          <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
            {lifecycle.versionImpact}
          </p>
          <p className="mt-3 border-t border-[var(--border-subtle)] pt-3 text-xs leading-5 text-[var(--text-tertiary)]">
            保存只记录当前冻结 Preview；不会激活、运行或调用 Provider。
          </p>
        </section>
      </div>

      {planNameLocked ? (
        <div className="mt-4 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
            Plan name（已锁定）
          </p>
          <p className="mt-1 break-words font-semibold text-[var(--text-primary)]">
            {planName}
          </p>
        </div>
      ) : (
        <div className="mt-4 max-w-xl">
          <label
            className="mb-2 block text-sm font-semibold text-[var(--text-primary)]"
            htmlFor="workflow-plan-name"
          >
            Plan name
          </label>
          <input
            aria-describedby={
              invalidName ? "workflow-plan-name-error" : undefined
            }
            aria-invalid={invalidName ? "true" : undefined}
            className="min-h-[var(--touch-target)] w-full rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--focus-1)] focus:shadow-[var(--focus-ring)]"
            id="workflow-plan-name"
            maxLength={200}
            onChange={(event) => onPlanNameChange(event.target.value)}
            placeholder="为新 WorkflowPlan 命名"
            value={planName}
          />
          {invalidName ? (
            <p
              className="mt-2 text-sm font-medium text-[var(--state-danger)]"
              id="workflow-plan-name-error"
              role="alert"
            >
              Plan name 去除首尾空格后必须为 1..200 个字符
            </p>
          ) : null}
        </div>
      )}

      {sourceVersionId ? (
        <p className="mt-3 break-all text-xs text-[var(--text-tertiary)]">
          草稿来源 {sourceVersionId}；并发基线始终使用 Plan 的最新当前 Version。
        </p>
      ) : null}

      {planningStatus === "held" ? (
        <p
          className="mt-4 rounded-[var(--radius-3)] border border-[var(--warning-1)] bg-[var(--warning-soft)] px-4 py-3 text-sm font-semibold text-[var(--state-warning)]"
          role="status"
        >
          held Preview 可以保存，但保存不会解除阻断、批准或启动运行。
        </p>
      ) : null}

      {message ? (
        <p
          className="mt-4 text-sm font-semibold text-[var(--state-success)]"
          role="status"
        >
          {message}
        </p>
      ) : null}
      {error ? (
        <p
          className="mt-4 text-sm font-semibold text-[var(--state-danger)]"
          role="alert"
        >
          {error}
        </p>
      ) : null}
      {lifecycleMessage ? (
        <p
          aria-live="polite"
          className="mt-4 rounded-[var(--radius-3)] border border-[var(--success-1)] bg-[var(--success-soft)] px-4 py-3 text-sm font-semibold text-[var(--state-success)]"
          role="status"
        >
          {lifecycleMessage}
        </p>
      ) : null}
      {lifecycleError ? (
        <p
          className="mt-4 rounded-[var(--radius-3)] border border-[var(--danger-1)] bg-[var(--danger-soft)] px-4 py-3 text-sm font-semibold text-[var(--state-danger)]"
          role="alert"
        >
          {lifecycleError}
        </p>
      ) : null}

      {planStatus ? (
        <section className="mt-4 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h4 className="font-semibold text-[var(--text-primary)]">
                Current Version 运行门禁
              </h4>
              <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                {runGate.status === "loading"
                  ? "正在读取门禁…"
                  : runGate.status === "error"
                    ? "门禁读取失败；不会假定当前 Version 可运行。"
                    : runGate.status === "ready" && runGate.runnable
                      ? "门禁已通过，可创建本地样例 Run。"
                      : runGate.status === "ready"
                        ? "门禁未通过；下方 Run 操作保持禁用并说明原因。"
                        : "等待已保存 Version 与 Plan 状态。"}
              </p>
            </div>
            <span
              className={`rounded-[var(--radius-pill)] px-2.5 py-1 text-xs font-semibold ${
                runGate.status === "ready" && runGate.runnable
                  ? "bg-[var(--success-soft)] text-[var(--state-success)]"
                  : "bg-[var(--warning-soft)] text-[var(--state-warning)]"
              }`}
            >
              {runGate.status === "ready" && runGate.runnable
                ? "可运行 · 本地样例"
                : "门禁中"}
            </span>
          </div>
          {runGate.status === "error" ? (
            <button
              className="mt-3 min-h-[var(--touch-target)] rounded-[var(--radius-3)] border border-[var(--border-strong)] bg-[var(--surface-primary)] px-3 py-2 text-sm font-semibold text-[var(--text-primary)] focus:outline-none focus:shadow-[var(--focus-ring)]"
              onClick={onRefreshGate}
              type="button"
            >
              重新读取门禁
            </button>
          ) : null}
        </section>
      ) : null}

      <div className="mt-5 grid min-w-0 gap-3 lg:grid-cols-2">
        <section
          className={`flex min-w-0 flex-col justify-between rounded-[var(--radius-3)] border p-4 ${
            saveAvailable
              ? "border-[var(--action-primary)] bg-[var(--surface-primary)]"
              : "border-[var(--border-subtle)] bg-[var(--surface-muted)]"
          }`}
        >
          <div>
            <p
              className={`text-xs font-semibold uppercase tracking-[0.14em] ${
                saveAvailable
                  ? "text-[var(--action-primary)]"
                  : "text-[var(--text-tertiary)]"
              }`}
            >
              {saveStateLabel}
            </p>
            <h4 className="mt-1 font-semibold text-[var(--text-primary)]">
              {saveAction?.label ?? "保存 Version"}
            </h4>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
              {saveAction?.reason}
            </p>
          </div>
          <button
            aria-busy={saving}
            className="mt-4 min-h-[var(--touch-target)] rounded-[var(--radius-3)] bg-[var(--action-primary)] px-4 py-2.5 text-sm font-semibold text-[var(--text-inverse)] transition-colors hover:bg-[var(--action-primary-hover)] focus:outline-none focus:shadow-[var(--focus-ring)] disabled:cursor-not-allowed disabled:bg-[var(--border-strong)]"
            data-testid="workflow-plan-save"
            disabled={!saveAvailable}
            onClick={onSave}
            type="button"
          >
            {saving ? "正在保存…" : retryable ? "重试保存" : "Save Preview"}
          </button>
        </section>

        <div className="grid min-w-0 gap-3 sm:grid-cols-3">
          {gatedActions.map((action) => {
            const reasonId = `planner-${action.key}-gate-reason`;
            const available = action.state === "available";
            return (
              <section
                className={`flex min-w-0 flex-col justify-between rounded-[var(--radius-3)] border p-3 ${
                  available
                    ? "border-[var(--action-primary)] bg-[var(--surface-primary)]"
                    : "border-[var(--border-subtle)] bg-[var(--surface-muted)]"
                }`}
                key={action.key}
              >
                <div>
                  <p
                    className={`text-xs font-semibold uppercase tracking-[0.12em] ${
                      available
                        ? "text-[var(--action-primary)]"
                        : "text-[var(--text-tertiary)]"
                    }`}
                  >
                    {action.state === "complete"
                      ? "已完成"
                      : action.state === "progress"
                        ? "处理中"
                        : available
                          ? "当前可执行"
                          : "需先完成"}
                  </p>
                  <p
                    className="mt-2 text-xs leading-5 text-[var(--text-secondary)]"
                    id={reasonId}
                  >
                    {action.reason}
                  </p>
                </div>
                <button
                  aria-describedby={reasonId}
                  aria-busy={action.state === "progress"}
                  className={`mt-3 min-h-[var(--touch-target)] rounded-[var(--radius-3)] px-3 py-2 text-sm font-semibold focus:outline-none focus:shadow-[var(--focus-ring)] ${
                    available
                      ? "bg-[var(--action-primary)] text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
                      : "border border-[var(--border-strong)] bg-[var(--surface-primary)] text-[var(--text-tertiary)] disabled:cursor-not-allowed"
                  }`}
                  data-testid={`workflow-plan-${action.key}`}
                  disabled={!available}
                  onClick={
                    action.key === "save"
                      ? undefined
                      : actionHandlers[action.key]
                  }
                  type="button"
                >
                  {action.label}
                </button>
              </section>
            );
          })}
        </div>
      </div>

      {runReceipt ? (
        <section className="mt-4 rounded-[var(--radius-3)] border border-[var(--success-1)] bg-[var(--success-soft)] p-4">
          <h4 className="font-semibold text-[var(--state-success)]">
            本地样例 Run 已创建
          </h4>
          <p className="mt-2 text-sm leading-6 text-[var(--text-primary)]">
            状态 {runReceipt.status}，{runReceipt.totalSteps} 个 Step，
            {runReceipt.recordsCount} 条记录。该回执不代表 live Provider 或生产运行。
          </p>
          <p className="mt-2 break-all font-mono text-xs text-[var(--text-tertiary)]">
            Run ID: {runReceipt.id}
          </p>
        </section>
      ) : null}
    </section>
  );
}
