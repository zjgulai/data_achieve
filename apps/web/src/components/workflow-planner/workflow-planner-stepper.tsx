import React from "react";

import type { PlannerStep } from "@/lib/workflow-planner";

type PlannerDisplayStep = PlannerStep | "review";

const plannerSteps: Array<{ key: PlannerDisplayStep; label: string }> = [
  { key: "mode", label: "模式与目标" },
  { key: "scopes", label: "Scope 与输入" },
  { key: "constraints", label: "交付与约束" },
  { key: "preview", label: "计划预览" },
  { key: "review", label: "Review 与保存" },
];

export function WorkflowPlannerStepper({
  currentStep,
  reviewReady = false,
}: {
  currentStep: PlannerStep;
  reviewReady?: boolean;
}) {
  const activeStep: PlannerDisplayStep =
    currentStep === "preview" && reviewReady ? "review" : currentStep;
  const activeIndex = plannerSteps.findIndex((step) => step.key === activeStep);

  return (
    <nav
      aria-label="Workflow Planner 步骤"
      data-testid="workflow-planner-stepper"
    >
      <ol className="grid min-w-0 gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {plannerSteps.map((step, index) => {
          const current = step.key === activeStep;
          const completed = index < activeIndex;
          return (
            <li
              aria-current={current ? "step" : undefined}
              className={`min-w-0 rounded-[var(--radius-2)] border px-3 py-3 text-sm ${
                current
                  ? "border-[var(--action-primary)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
                  : completed
                    ? "border-[var(--border-subtle)] bg-[var(--surface-secondary)] text-[var(--state-success)]"
                    : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-tertiary)]"
              }`}
              key={step.key}
            >
              <span className="block text-xs font-semibold">
                {index + 1} ·{" "}
                {current ? "当前步骤" : completed ? "已完成" : "待进入"}
              </span>
              <span className="mt-1 block font-semibold">{step.label}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
