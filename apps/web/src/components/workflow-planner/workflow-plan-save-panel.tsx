"use client";

import type {
  WorkflowPlannerMode,
  WorkflowPlanningStatus,
} from "@/types/workflow-planner";

type WorkflowPlanSavePanelProps = {
  planName: string;
  planNameLocked: boolean;
  mode: WorkflowPlannerMode;
  currentVersionNumber: number | null;
  sourceVersionId: string | null;
  planningStatus: WorkflowPlanningStatus;
  saving: boolean;
  canSave: boolean;
  message: string | null;
  error: string | null;
  retryable: boolean;
  onPlanNameChange: (name: string) => void;
  onSave: () => void;
};

export function WorkflowPlanSavePanel({
  planName,
  planNameLocked,
  mode,
  currentVersionNumber,
  sourceVersionId,
  planningStatus,
  saving,
  canSave,
  message,
  error,
  retryable,
  onPlanNameChange,
  onSave,
}: WorkflowPlanSavePanelProps) {
  const trimmedNameLength = planName.trim().length;
  const invalidName =
    !planNameLocked && (trimmedNameLength < 1 || trimmedNameLength > 200);

  return (
    <section
      className="min-w-0 rounded-2xl border border-[#DCCDC5] bg-[#FFFDFC] p-5"
      data-testid="workflow-plan-save-panel"
    >
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#9A7467]">
            Explicit persistence
          </p>
          <h3 className="mt-1 text-lg font-semibold text-[#392823]">
            Save Preview
          </h3>
        </div>
        <p className="text-sm font-semibold text-[#6D514A]">
          {mode === "periodic_monitoring" ? "周期监测" : "批量研究"}
          {currentVersionNumber === null
            ? " · 新 Plan"
            : ` · 当前基线 v${currentVersionNumber}`}
        </p>
      </div>

      {planNameLocked ? (
        <div className="mt-4 rounded-xl border border-[#E8DDD6] bg-[#FBF8F5] px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#9A7467]">
            Plan name（已锁定）
          </p>
          <p className="mt-1 break-words font-semibold text-[#392823]">
            {planName}
          </p>
        </div>
      ) : (
        <div className="mt-4 max-w-xl">
          <label
            className="mb-2 block text-sm font-semibold text-[#463530]"
            htmlFor="workflow-plan-name"
          >
            Plan name
          </label>
          <input
            aria-describedby={
              invalidName ? "workflow-plan-name-error" : undefined
            }
            aria-invalid={invalidName ? "true" : undefined}
            className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#C97865]"
            id="workflow-plan-name"
            maxLength={200}
            onChange={(event) => onPlanNameChange(event.target.value)}
            placeholder="为新 WorkflowPlan 命名"
            value={planName}
          />
          {invalidName ? (
            <p
              className="mt-2 text-sm font-medium text-[#B85F4F]"
              id="workflow-plan-name-error"
              role="alert"
            >
              Plan name 去除首尾空格后必须为 1..200 个字符
            </p>
          ) : null}
        </div>
      )}

      {sourceVersionId ? (
        <p className="mt-3 break-all text-xs text-[#716562]">
          草稿来源 {sourceVersionId}；并发基线始终使用 Plan 的最新当前 Version。
        </p>
      ) : null}

      {planningStatus === "held" ? (
        <p
          className="mt-4 rounded-xl border border-[#E4B9A7] bg-[#FFF5EF] px-4 py-3 text-sm font-semibold text-[#803F32]"
          role="status"
        >
          held Preview 可以保存，但保存不会解除阻断、批准或启动运行。
        </p>
      ) : null}

      <p className="mt-4 text-sm leading-6 text-[#716562]">
        保存只记录当前冻结 Preview；不会激活、运行或调用 Provider。
      </p>

      {message ? (
        <p className="mt-4 text-sm font-semibold text-[#356152]" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="mt-4 text-sm font-semibold text-[#B85F4F]" role="alert">
          {error}
        </p>
      ) : null}

      <button
        aria-busy={saving}
        className="mt-5 rounded-xl bg-[#9F4E3D] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-[#CDBEB9]"
        data-testid="workflow-plan-save"
        disabled={!canSave || saving}
        onClick={onSave}
        type="button"
      >
        {saving ? "正在保存…" : retryable ? "重试保存" : "Save Preview"}
      </button>
    </section>
  );
}
