"use client";

import { useRef, useState } from "react";

import { WorkflowPlanAdvancedView } from "@/components/workflow-planner/workflow-plan-advanced-view";
import { WorkflowPlanSimpleView } from "@/components/workflow-planner/workflow-plan-simple-view";
import type { WorkflowPlanPreview as WorkflowPlanPreviewValue } from "@/types/workflow-planner";

type PreviewTab = "simple" | "advanced";

const tabs: Array<{ key: PreviewTab; label: string }> = [
  { key: "simple", label: "简单视图" },
  { key: "advanced", label: "高级视图" },
];

export function WorkflowPlanPreview({
  preview,
  stale,
}: {
  preview: WorkflowPlanPreviewValue;
  stale: boolean;
}) {
  const [activeTab, setActiveTab] = useState<PreviewTab>("simple");
  const tabRefs = useRef<Record<PreviewTab, HTMLButtonElement | null>>({
    simple: null,
    advanced: null,
  });

  function selectTab(tab: PreviewTab, focus = false) {
    setActiveTab(tab);
    if (focus) {
      tabRefs.current[tab]?.focus();
    }
  }

  function onTabKeyDown(
    event: React.KeyboardEvent<HTMLButtonElement>,
    current: PreviewTab,
  ) {
    const currentIndex = tabs.findIndex((tab) => tab.key === current);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tabs.length - 1;
    }
    if (nextIndex !== null) {
      event.preventDefault();
      const next = tabs[nextIndex];
      if (next) {
        selectTab(next.key, true);
      }
    }
  }

  return (
    <section
      className="min-w-0 space-y-4"
      data-testid="workflow-planner-preview"
    >
      {stale ? (
        <div
          className="rounded-xl border border-[#E4B9A7] bg-[#FFF5EF] px-4 py-3 text-sm font-semibold text-[#803F32]"
          data-testid="workflow-planner-stale"
          role="status"
        >
          此 Preview 已过期；请按当前输入重新生成。
        </div>
      ) : null}

      <div
        aria-label="WorkflowPlan Preview 视图"
        className="flex min-w-0 flex-wrap gap-2"
        role="tablist"
      >
        {tabs.map((tab) => {
          const selected = activeTab === tab.key;
          return (
            <button
              aria-controls={`workflow-planner-${tab.key}-panel`}
              aria-selected={selected}
              className={`rounded-xl px-4 py-2 text-sm font-semibold ${
                selected
                  ? "bg-[#9F4E3D] text-white"
                  : "border border-[#DCCFC8] bg-white text-[#6D514A]"
              }`}
              id={`workflow-planner-${tab.key}-tab`}
              key={tab.key}
              onClick={() => selectTab(tab.key)}
              onKeyDown={(event) => onTabKeyDown(event, tab.key)}
              ref={(element) => {
                tabRefs.current[tab.key] = element;
              }}
              role="tab"
              tabIndex={selected ? 0 : -1}
              type="button"
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div
        aria-labelledby="workflow-planner-simple-tab"
        className="min-w-0"
        hidden={activeTab !== "simple"}
        id="workflow-planner-simple-panel"
        role="tabpanel"
        tabIndex={activeTab === "simple" ? 0 : -1}
      >
        {activeTab === "simple" ? (
          <WorkflowPlanSimpleView preview={preview} />
        ) : null}
      </div>
      <div
        aria-labelledby="workflow-planner-advanced-tab"
        className="min-w-0"
        hidden={activeTab !== "advanced"}
        id="workflow-planner-advanced-panel"
        role="tabpanel"
        tabIndex={activeTab === "advanced" ? 0 : -1}
      >
        {activeTab === "advanced" ? (
          <WorkflowPlanAdvancedView preview={preview} />
        ) : null}
      </div>
    </section>
  );
}
