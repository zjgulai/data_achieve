import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkflowPlanSavePanel } from "@/components/workflow-planner/workflow-plan-save-panel";
import { WorkflowPlannerStepper } from "@/components/workflow-planner/workflow-planner-stepper";
import { buildPlannerLifecyclePresentation } from "@/lib/workflow-planner-lifecycle";

describe("workflow planner lifecycle presentation", () => {
  it("keeps Save distinct until an immutable Version exists", () => {
    const presentation = buildPlannerLifecyclePresentation({
      activeAction: null,
      canSave: true,
      currentVersionNumber: null,
      hasSavedReceipt: false,
      hasUnsavedChanges: true,
      planStatus: null,
      runCreated: false,
      runGate: { status: "idle", runnable: false, blockerCodes: [] },
      missingOptionalFields: [],
      planningStatus: "resolved",
      saving: false,
    });

    expect(presentation.versionImpact).toContain("创建不可变 Version v1");
    expect(presentation.actions).toEqual([
      expect.objectContaining({ key: "save", state: "available" }),
      expect.objectContaining({ key: "approve", state: "blocked" }),
      expect.objectContaining({ key: "activate", state: "blocked" }),
      expect.objectContaining({ key: "run", state: "blocked" }),
    ]);
    expect(
      presentation.actions.find((action) => action.key === "run")?.reason,
    ).toContain("保存");
  });

  it("opens approval, activation and fixture Run one gate at a time", () => {
    const approved = buildPlannerLifecyclePresentation({
      activeAction: null,
      canSave: true,
      currentVersionNumber: 2,
      hasSavedReceipt: true,
      hasUnsavedChanges: false,
      planStatus: "previewed",
      runCreated: false,
      runGate: {
        status: "ready",
        runnable: false,
        blockerCodes: ["workflow_plan_not_active"],
      },
      missingOptionalFields: [],
      planningStatus: "resolved",
      saving: false,
    });
    expect(approved.actions).toEqual([
      expect.objectContaining({ key: "save", state: "complete" }),
      expect.objectContaining({ key: "approve", state: "available" }),
      expect.objectContaining({ key: "activate", state: "blocked" }),
      expect.objectContaining({ key: "run", state: "blocked" }),
    ]);

    const runnable = buildPlannerLifecyclePresentation({
      activeAction: null,
      canSave: true,
      currentVersionNumber: 2,
      hasSavedReceipt: true,
      hasUnsavedChanges: false,
      planStatus: "active",
      runCreated: false,
      runGate: { status: "ready", runnable: true, blockerCodes: [] },
      missingOptionalFields: [],
      planningStatus: "resolved",
      saving: false,
    });
    expect(runnable.actions).toEqual([
      expect.objectContaining({ key: "save", state: "complete" }),
      expect.objectContaining({ key: "approve", state: "complete" }),
      expect.objectContaining({ key: "activate", state: "complete" }),
      expect.objectContaining({ key: "run", state: "available" }),
    ]);
  });

  it("explains held impact and a non-destructive recovery path", () => {
    const presentation = buildPlannerLifecyclePresentation({
      activeAction: null,
      canSave: true,
      currentVersionNumber: 3,
      hasSavedReceipt: false,
      hasUnsavedChanges: true,
      planStatus: "previewed",
      runCreated: false,
      runGate: {
        status: "ready",
        runnable: false,
        blockerCodes: ["workflow_version_contract_not_runnable"],
      },
      missingOptionalFields: ["comments", "author_profile"],
      planningStatus: "held",
      saving: false,
    });

    expect(presentation.statusLabel).toBe("已暂停，等待处理");
    expect(presentation.cause).toContain("没有可进入执行阶段的完整路线");
    expect(presentation.impact).toContain("仍可保存为审阅证据");
    expect(presentation.nextAction).toContain("返回 Scope");
    expect(presentation.missingFields).toEqual(["author_profile", "comments"]);
    expect(presentation.versionImpact).toContain("v3");
    expect(presentation.versionImpact).toContain("v4");
  });

  it("renders five phases and activates Review only after a current Preview", () => {
    const previewMarkup = renderToStaticMarkup(
      createElement(WorkflowPlannerStepper, {
        currentStep: "preview",
        reviewReady: false,
      }),
    );
    const reviewMarkup = renderToStaticMarkup(
      createElement(WorkflowPlannerStepper, {
        currentStep: "preview",
        reviewReady: true,
      }),
    );

    expect(previewMarkup.match(/<li/g)).toHaveLength(5);
    expect(previewMarkup).toContain('aria-current="step"');
    expect(previewMarkup).toContain("计划预览");
    expect(reviewMarkup).toContain("Review 与保存");
    expect(reviewMarkup).toContain("当前步骤");
  });

  it("renders one available lifecycle action with explicit local-run boundaries", () => {
    const markup = renderToStaticMarkup(
      createElement(WorkflowPlanSavePanel, {
        activeAction: null,
        approvalReasonCount: 2,
        canSave: true,
        currentVersionNumber: 2,
        error: null,
        hasUnsavedChanges: false,
        lifecycleError: null,
        lifecycleMessage: null,
        message: null,
        missingOptionalFields: ["comments"],
        mode: "batch_research",
        onActivate: () => undefined,
        onApprove: () => undefined,
        onPlanNameChange: () => undefined,
        onRefreshGate: () => undefined,
        onRun: () => undefined,
        onSave: () => undefined,
        planName: "Research plan",
        planNameLocked: true,
        planStatus: "approved",
        planningStatus: "partially_resolved",
        retryable: false,
        runGate: {
          status: "ready",
          runnable: false,
          blockerCodes: ["workflow_plan_not_active"],
        },
        runReceipt: null,
        saving: false,
        sourceVersionId: null,
      }),
    );

    expect(markup).toContain("Review 与保存");
    expect(markup).toContain("版本影响");
    expect(markup).toContain("2 条路线原因仍需处理");
    expect(markup).toContain("批准 Plan");
    expect(markup).toContain("激活 Plan");
    expect(markup).toContain("创建本地样例 Run");
    expect(markup).toContain("门禁未通过");
    expect(markup.match(/disabled=""/g)).toHaveLength(3);
  });
});
