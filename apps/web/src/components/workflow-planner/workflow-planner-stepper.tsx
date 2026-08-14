import type { PlannerStep } from "@/lib/workflow-planner";

const plannerSteps: Array<{ key: PlannerStep; label: string }> = [
  { key: "mode", label: "模式与目标" },
  { key: "scopes", label: "Scope 与输入" },
  { key: "constraints", label: "约束" },
  { key: "preview", label: "计划预览" },
];

export function WorkflowPlannerStepper({
  currentStep,
}: {
  currentStep: PlannerStep;
}) {
  return (
    <nav aria-label="Workflow Planner 步骤">
      <ol className="grid min-w-0 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {plannerSteps.map((step, index) => {
          const current = step.key === currentStep;
          return (
            <li
              aria-current={current ? "step" : undefined}
              className={`min-w-0 rounded-xl border px-3 py-3 text-sm ${
                current
                  ? "border-[#C97865] bg-[#FFF6F1] text-[#7A3326]"
                  : "border-[#E9E5E2] bg-[#FFFDFC] text-[#6D6260]"
              }`}
              key={step.key}
            >
              <span className="mr-2 font-semibold">{index + 1}</span>
              <span>{step.label}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
