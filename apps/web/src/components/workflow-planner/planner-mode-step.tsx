"use client";

import {
  createWorkflowPlannerDraft,
  plannerFieldErrorId,
  type PlannerFieldErrors,
  type WorkflowPlannerDraft,
} from "@/lib/workflow-planner";
import type {
  WorkflowPlannerMode,
  WorkflowPlannerPurpose,
} from "@/types/workflow-planner";

type PlannerModeStepProps = {
  draft: WorkflowPlannerDraft;
  fieldErrors: PlannerFieldErrors;
  onDraftChange: (draft: WorkflowPlannerDraft) => void;
  modeLocked?: boolean;
};

function FieldError({
  fieldId,
  fieldErrors,
}: {
  fieldId: string;
  fieldErrors: PlannerFieldErrors;
}) {
  const message = fieldErrors[fieldId];
  return message ? (
    <p
      className="mt-2 text-sm font-medium text-[#B85F4F]"
      id={plannerFieldErrorId(fieldId)}
      role="alert"
    >
      {message}
    </p>
  ) : null;
}

const modeOptions: Array<{
  value: WorkflowPlannerMode;
  title: string;
  description: string;
}> = [
  {
    value: "periodic_monitoring",
    title: "周期监测",
    description: "规划持续监测、增量更新与交付意图。",
  },
  {
    value: "batch_research",
    title: "批量研究",
    description: "规划一次性的关键词检索与 Seed URL 解析。",
  },
];

export function PlannerModeStep({
  draft,
  fieldErrors,
  onDraftChange,
  modeLocked = false,
}: PlannerModeStepProps) {
  const modeError = fieldErrors["planner-mode"];
  const purposeError = fieldErrors["planner-purpose"];

  function changeMode(mode: WorkflowPlannerMode) {
    if (!modeLocked && mode !== draft.mode) {
      onDraftChange(createWorkflowPlannerDraft(mode));
    }
  }

  function changePurpose(purpose: WorkflowPlannerPurpose) {
    onDraftChange({ ...draft, purpose, revision: draft.revision + 1 });
  }

  return (
    <section aria-labelledby="planner-mode-heading" className="min-w-0">
      <div className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#9A7467]">
          Step 1
        </p>
        <h2
          className="mt-2 text-xl font-semibold text-[#2E201C]"
          id="planner-mode-heading"
        >
          选择规划模式与业务目标
        </h2>
      </div>

      <fieldset
        aria-describedby={
          modeError ? plannerFieldErrorId("planner-mode") : undefined
        }
        aria-invalid={modeError ? "true" : undefined}
        className="grid min-w-0 gap-3 md:grid-cols-2"
        id="planner-mode"
        tabIndex={modeError ? -1 : undefined}
      >
        <legend className="sr-only">规划模式</legend>
        {modeOptions.map((option) => {
          const id = `planner-mode-${option.value}`;
          return (
            <label
              className="flex min-w-0 cursor-pointer gap-3 rounded-2xl border border-[#E8DDD6] bg-[#FFFDFC] p-4 has-[:checked]:border-[#C97865] has-[:checked]:bg-[#FFF6F1]"
              htmlFor={id}
              key={option.value}
            >
              <input
                checked={draft.mode === option.value}
                disabled={modeLocked}
                id={id}
                name="planner-mode"
                onChange={() => changeMode(option.value)}
                type="radio"
                value={option.value}
              />
              <span className="min-w-0">
                <span className="block font-semibold text-[#392823]">
                  {option.title}
                </span>
                <span className="mt-1 block text-sm leading-6 text-[#716562]">
                  {option.description}
                </span>
              </span>
            </label>
          );
        })}
      </fieldset>
      <FieldError fieldErrors={fieldErrors} fieldId="planner-mode" />
      {modeLocked ? (
        <p className="mt-2 text-sm text-[#716562]">
          已保存 Plan 的 mode 已锁定；如需切换 mode，请新建 Plan。
        </p>
      ) : null}

      <div className="mt-6 max-w-xl">
        <label
          className="mb-2 block text-sm font-semibold text-[#463530]"
          htmlFor="planner-purpose"
        >
          业务目标
        </label>
        <select
          aria-describedby={
            purposeError ? plannerFieldErrorId("planner-purpose") : undefined
          }
          aria-invalid={purposeError ? "true" : undefined}
          className="w-full rounded-xl border border-[#DED3CC] bg-white px-3 py-2.5 text-sm outline-none focus:border-[#C97865]"
          id="planner-purpose"
          onChange={(event) =>
            changePurpose(event.target.value as WorkflowPlannerPurpose)
          }
          value={draft.purpose}
        >
          <option value="brand_monitoring">品牌监测</option>
          <option value="market_research">市场研究</option>
          <option value="competitive_research">竞品研究</option>
        </select>
        <FieldError fieldErrors={fieldErrors} fieldId="planner-purpose" />
      </div>
    </section>
  );
}
