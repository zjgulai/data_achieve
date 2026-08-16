import type { WorkflowPlanStatus } from "@/types/workflow-plan-persistence";
import type { WorkflowFixtureRunGateBlockerCode } from "@/types/workflow-run";
import type { WorkflowPlanningStatus } from "@/types/workflow-planner";

export type PlannerLifecycleActionKey = "save" | "approve" | "activate" | "run";

export type PlannerLifecycleActionState =
  | "available"
  | "progress"
  | "complete"
  | "blocked";

export type PlannerLifecycleAction = {
  key: PlannerLifecycleActionKey;
  label: string;
  reason: string;
  state: PlannerLifecycleActionState;
};

export type PlannerLifecyclePresentation = {
  actions: PlannerLifecycleAction[];
  cause: string;
  impact: string;
  missingFields: string[];
  nextAction: string;
  statusLabel: string;
  versionImpact: string;
};

type PlannerLifecycleInput = {
  activeAction: PlannerLifecycleActionKey | null;
  canSave: boolean;
  currentVersionNumber: number | null;
  hasSavedReceipt: boolean;
  hasUnsavedChanges: boolean;
  planStatus: WorkflowPlanStatus | null;
  runCreated: boolean;
  runGate: {
    status: "idle" | "loading" | "ready" | "error";
    runnable: boolean;
    blockerCodes: readonly WorkflowFixtureRunGateBlockerCode[];
  };
  missingOptionalFields: readonly string[];
  planningStatus: WorkflowPlanningStatus;
  saving: boolean;
};

function planningSummary(
  status: WorkflowPlanningStatus,
): Pick<
  PlannerLifecyclePresentation,
  "cause" | "impact" | "nextAction" | "statusLabel"
> {
  if (status === "held") {
    return {
      statusLabel: "已暂停，等待处理",
      cause: "当前规划没有可进入执行阶段的完整路线。",
      impact: "仍可保存为审阅证据；批准、激活和本地样例运行由独立门禁决定。",
      nextAction: "返回 Scope、字段或约束配置，处理阻断后重新生成 Preview。",
    };
  }
  if (status === "partially_resolved") {
    return {
      statusLabel: "部分路线待处理",
      cause: "部分路线仍需审批，或缺少可选字段与完整覆盖。",
      impact: "可以保存当前规划证据，但 runnable gate 会继续阻止运行。",
      nextAction: "复核缺失字段与审批原因，再决定修改配置或保存审阅版本。",
    };
  }
  return {
    statusLabel: "规划已解析",
    cause: "当前 Preview 的路线、Scope 与约束已完成规划解析。",
    impact: "保存、批准、激活和本地样例运行仍需按顺序获得各自服务端回执。",
    nextAction: "复核版本影响并显式保存不可变 Version。",
  };
}

function saveAction(input: PlannerLifecycleInput): PlannerLifecycleAction {
  if (
    input.planStatus !== null &&
    !input.hasUnsavedChanges &&
    (input.hasSavedReceipt || input.planStatus !== "previewed") &&
    input.activeAction !== "save"
  ) {
    return {
      key: "save",
      label: "保存 Version",
      reason: input.hasSavedReceipt
        ? "已收到持久化回执；保存没有隐式批准、激活或运行。"
        : "当前编辑与已保存 Version 一致，无需重复保存。",
      state: "complete",
    };
  }
  if (input.saving) {
    return {
      key: "save",
      label: "保存 Version",
      reason: "正在等待服务端持久化回执。",
      state: "progress",
    };
  }
  if (input.canSave) {
    return {
      key: "save",
      label: "保存 Version",
      reason: "唯一可执行动作；只保存当前冻结 Preview。",
      state: "available",
    };
  }
  return {
    key: "save",
    label: "保存 Version",
    reason: "先生成当前 Preview，并完成有效的 Plan name 与 Project 上下文。",
    state: "blocked",
  };
}

function approveAction(input: PlannerLifecycleInput): PlannerLifecycleAction {
  if (input.activeAction === "approve") {
    return {
      key: "approve",
      label: "批准 Plan",
      reason: "正在等待服务端生命周期回执；不会启动运行。",
      state: "progress",
    };
  }
  if (
    input.planStatus === "approved" ||
    input.planStatus === "active" ||
    input.planStatus === "paused" ||
    input.planStatus === "archived"
  ) {
    return {
      key: "approve",
      label: "批准 Plan",
      reason: "Plan 已通过本地生命周期批准状态。",
      state: "complete",
    };
  }
  if (
    input.planStatus === "previewed" &&
    !input.hasUnsavedChanges &&
    input.hasSavedReceipt
  ) {
    return {
      key: "approve",
      label: "批准 Plan",
      reason:
        "将 Plan 从 previewed 变更为 approved；仅写入本地生命周期状态，不调用 Provider。",
      state: "available",
    };
  }
  return {
    key: "approve",
    label: "批准 Plan",
    reason:
      input.planStatus === null
        ? "先保存不可变 Version。"
        : "先保存并确认当前 Preview；未保存修改不能被批准。",
    state: "blocked",
  };
}

function activateAction(input: PlannerLifecycleInput): PlannerLifecycleAction {
  if (input.activeAction === "activate") {
    return {
      key: "activate",
      label: "激活 Plan",
      reason: "正在等待 active 状态回执；active 仍不自动等于 runnable。",
      state: "progress",
    };
  }
  if (
    input.planStatus === "active" ||
    input.planStatus === "paused" ||
    input.planStatus === "archived"
  ) {
    return {
      key: "activate",
      label: "激活 Plan",
      reason:
        input.planStatus === "active"
          ? "Plan 已激活；仍需读取 runnable Version gate。"
          : "Plan 已进入后续生命周期状态。",
      state: "complete",
    };
  }
  if (input.planStatus === "approved" && !input.hasUnsavedChanges) {
    return {
      key: "activate",
      label: "激活 Plan",
      reason:
        "将 approved Plan 变更为 active；完成后再读取 runnable gate，不会自动运行。",
      state: "available",
    };
  }
  return {
    key: "activate",
    label: "激活 Plan",
    reason: "先获得批准回执；active 与 runnable 是两个独立状态。",
    state: "blocked",
  };
}

const blockerLabels: Record<WorkflowFixtureRunGateBlockerCode, string> = {
  project_not_active: "Project 未激活",
  workflow_plan_not_active: "Plan 未激活",
  workflow_version_not_current: "当前选择不是最新 Version",
  workflow_version_contract_not_runnable: "Version 执行合同不完整",
};

function runAction(input: PlannerLifecycleInput): PlannerLifecycleAction {
  if (input.runCreated) {
    return {
      key: "run",
      label: "创建本地样例 Run",
      reason: "已收到本地 Run 回执；未调用 Provider、凭证、浏览器或 LLM。",
      state: "complete",
    };
  }
  if (input.activeAction === "run") {
    return {
      key: "run",
      label: "创建本地样例 Run",
      reason: "正在等待本地 fixture Run 与 Step 回执。",
      state: "progress",
    };
  }
  if (input.hasUnsavedChanges) {
    return {
      key: "run",
      label: "创建本地样例 Run",
      reason: "当前有未保存修改；Run 只能绑定已保存的 current Version。",
      state: "blocked",
    };
  }
  if (input.planStatus !== "active") {
    return {
      key: "run",
      label: "创建本地样例 Run",
      reason: "先批准并激活 Plan，再读取 runnable gate。",
      state: "blocked",
    };
  }
  if (input.runGate.status === "loading") {
    return {
      key: "run",
      label: "创建本地样例 Run",
      reason: "正在读取 current Version 的 runnable gate。",
      state: "progress",
    };
  }
  if (input.runGate.status === "error") {
    return {
      key: "run",
      label: "创建本地样例 Run",
      reason: "runnable gate 读取失败；刷新门禁后再决定是否运行。",
      state: "blocked",
    };
  }
  if (input.runGate.status === "ready" && input.runGate.runnable) {
    return {
      key: "run",
      label: "创建本地样例 Run",
      reason:
        "只创建 fixture Run/Step 证据；不会读取 API Key、调用 Provider 或写入生产。",
      state: "available",
    };
  }
  if (input.runGate.status === "ready") {
    const blockers = input.runGate.blockerCodes.map(
      (code) => blockerLabels[code],
    );
    return {
      key: "run",
      label: "创建本地样例 Run",
      reason: `runnable gate 已阻止：${blockers.join("、") || "合同未满足"}。`,
      state: "blocked",
    };
  }
  return {
    key: "run",
    label: "创建本地样例 Run",
    reason: "保存并激活 Plan 后读取 runnable gate。",
    state: "blocked",
  };
}

export function buildPlannerLifecyclePresentation(
  input: PlannerLifecycleInput,
): PlannerLifecyclePresentation {
  const summary = planningSummary(input.planningStatus);
  const missingFields = [...new Set(input.missingOptionalFields)].sort();
  const versionImpact =
    input.currentVersionNumber === null
      ? "新 Plan：保存会创建不可变 Version v1；不会审批、激活或运行。"
      : `当前 v${input.currentVersionNumber}：语义变化时创建 v${input.currentVersionNumber + 1}；语义未变化时保持 v${input.currentVersionNumber}。`;

  return {
    ...summary,
    missingFields,
    versionImpact,
    actions: [
      saveAction(input),
      approveAction(input),
      activateAction(input),
      runAction(input),
    ],
  };
}
