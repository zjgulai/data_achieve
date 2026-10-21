/**
 * 工作台页面的纯状态推导。
 *
 * 本模块不发请求，也不依赖 React。
 * 页面把后端数据传进来，本模块返回五步状态与页面四态。
 * 测试直接导入本模块，不需要浏览器。
 */

/** 五步流程的键。顺序与页面一致。 */
export type WorkbenchStepKey =
  | "question"
  | "plan"
  | "collect"
  | "analyze"
  | "report";

/** 步骤状态。 */
export type WorkbenchStepStatus =
  | "pending"
  | "active"
  | "done"
  | "blocked"
  | "failed";

/** 页面数据四态。 */
export type WorkbenchDataState = "loading" | "error" | "empty" | "ready";

/** 步骤显示所需的最小字段。 */
export type WorkbenchStep = {
  key: WorkbenchStepKey;
  title: string;
  /** 该步骤对应的门禁。来自 Playbook 1.3。 */
  gate: string;
  status: WorkbenchStepStatus;
  /** 状态说明。含下一步动作或阻断原因。 */
  detail: string;
  /** 状态来源。写明接口或本地输入。 */
  source: string;
};

/**
 * 页面依赖但后端缺少的工作台端点。
 *
 * 清单来自《模块设计》§3.11。
 * 页面与测试共用这一份清单。后端补齐一项，就改这里。
 */
export const MISSING_WORKBENCH_ENDPOINTS = {
  createTask: "POST /api/workbench/tasks",
  listTasks: "GET /api/workbench/tasks",
  getTask: "GET /api/workbench/tasks/{task_id}",
  previewPlan: "POST /api/workbench/plans/preview",
  updatePlan: "PATCH /api/workbench/plans/{plan_id}",
  approvePlan: "POST /api/workbench/plans/{plan_id}/approve",
  listGates: "GET /api/workbench/tasks/{task_id}/gates",
  listRuns: "GET /api/runs",
} as const;

/** 缺少的端点清单。按页面出现顺序排列。 */
export const MISSING_WORKBENCH_ENDPOINT_LIST: readonly string[] = [
  MISSING_WORKBENCH_ENDPOINTS.createTask,
  MISSING_WORKBENCH_ENDPOINTS.listTasks,
  MISSING_WORKBENCH_ENDPOINTS.getTask,
  MISSING_WORKBENCH_ENDPOINTS.previewPlan,
  MISSING_WORKBENCH_ENDPOINTS.updatePlan,
  MISSING_WORKBENCH_ENDPOINTS.approvePlan,
  MISSING_WORKBENCH_ENDPOINTS.listGates,
  MISSING_WORKBENCH_ENDPOINTS.listRuns,
];

/** 步骤标题。 */
const STEP_TITLES: Record<WorkbenchStepKey, string> = {
  question: "问题",
  plan: "计划",
  collect: "采集",
  analyze: "分析",
  report: "报告",
};

/** 步骤与门禁的对应关系。来自 Playbook 1.3 的阶段表。 */
const STEP_GATES: Record<WorkbenchStepKey, string> = {
  question: "G-Plan",
  plan: "G-Plan · G-Cost",
  collect: "G-Cost",
  analyze: "G-Evidence · G-Claim",
  report: "G-Publish",
};

/** 运行摘要。`GET /api/tasks/runs` 的响应满足本类型。 */
export type WorkbenchRunSummary = {
  id: string;
  status: string;
  records_count: number;
  error_message: string | null;
};

/** 报告摘要。`GET /api/reports` 的响应满足本类型。 */
export type WorkbenchReportSummary = {
  id: string;
  title: string;
  status: string;
};

/** 五步状态的输入。 */
export type WorkbenchStepInput = {
  question: string;
  latestRun: WorkbenchRunSummary | null;
  latestReport: WorkbenchReportSummary | null;
};

/** 构造一条步骤。 */
function makeStep(
  key: WorkbenchStepKey,
  status: WorkbenchStepStatus,
  detail: string,
  source: string
): WorkbenchStep {
  return {
    key,
    title: STEP_TITLES[key],
    gate: STEP_GATES[key],
    status,
    detail,
    source,
  };
}

/** 截短 ID。只用于显示。 */
function shortId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id;
}

/** 问题步骤。状态来自本地输入。 */
function questionStep(question: string): WorkbenchStep {
  if (question.trim() === "") {
    return makeStep("question", "pending", "填入决策问题后开始。", "本地输入");
  }
  return makeStep(
    "question",
    "active",
    `问题已填写。保存任务单需要 ${MISSING_WORKBENCH_ENDPOINTS.createTask}（未实现）。`,
    "本地输入"
  );
}

/** 计划步骤。状态来自计划预览端点。 */
function planStep(): WorkbenchStep {
  return makeStep(
    "plan",
    "blocked",
    `后端缺 ${MISSING_WORKBENCH_ENDPOINTS.previewPlan}，无法生成计划单。`,
    MISSING_WORKBENCH_ENDPOINTS.previewPlan
  );
}

/** 采集步骤。状态来自 `GET /api/tasks/runs`。 */
function collectStep(latestRun: WorkbenchRunSummary | null): WorkbenchStep {
  const source = "GET /api/tasks/runs";
  if (latestRun === null) {
    return makeStep("collect", "pending", "还没有运行。先到运行页发起一次采集。", source);
  }

  if (latestRun.status === "running" || latestRun.status === "pending") {
    return makeStep(
      "collect",
      "active",
      `运行 ${shortId(latestRun.id)} 正在进行。`,
      source
    );
  }

  if (latestRun.status === "failed") {
    return makeStep(
      "collect",
      "failed",
      latestRun.error_message ?? `运行 ${shortId(latestRun.id)} 失败。`,
      source
    );
  }

  if (
    latestRun.status === "success" ||
    latestRun.status === "completed" ||
    latestRun.status === "partial_success" ||
    latestRun.status === "empty"
  ) {
    const tail = latestRun.records_count === 0 ? "没有取到记录。" : `取到 ${latestRun.records_count} 条记录。`;
    return makeStep(
      "collect",
      "done",
      `运行 ${shortId(latestRun.id)} 已结束。${tail}`,
      source
    );
  }

  return makeStep(
    "collect",
    "active",
    `运行 ${shortId(latestRun.id)} 的状态是 ${latestRun.status}。`,
    source
  );
}

/** 分析步骤。状态来自运行结果端点。 */
function analyzeStep(): WorkbenchStep {
  return makeStep(
    "analyze",
    "blocked",
    `后端缺 ${MISSING_WORKBENCH_ENDPOINTS.listRuns} 列表端点，无法自动发现运行。运行结果端点 GET /api/runs/{run_id}/outcome 已就绪。`,
    "GET /api/runs/{run_id}/outcome"
  );
}

/** 报告步骤。状态来自 `GET /api/reports`。 */
function reportStep(latestReport: WorkbenchReportSummary | null): WorkbenchStep {
  const source = "GET /api/reports";
  if (latestReport === null) {
    return makeStep("report", "pending", "还没有报告。报告依赖计划与分析。", source);
  }
  return makeStep(
    "report",
    "done",
    `最近报告：${latestReport.title}（${latestReport.status}）。`,
    source
  );
}

/** 按固定顺序返回五步状态。 */
export function buildWorkbenchSteps(input: WorkbenchStepInput): WorkbenchStep[] {
  return [
    questionStep(input.question),
    planStep(),
    collectStep(input.latestRun),
    analyzeStep(),
    reportStep(input.latestReport),
  ];
}

/** 当前步骤。取第一个未完成的步骤。全部完成时返回 null。 */
export function currentStepKey(
  steps: readonly WorkbenchStep[]
): WorkbenchStepKey | null {
  const found = steps.find(step => step.status !== "done");
  return found ? found.key : null;
}

/**
 * 页面数据四态。
 *
 * 优先级固定：加载 → 错误 → 空 → 就绪。
 * 重新加载时保留旧数据，所以错误优先于旧数据。
 */
export function workbenchDataState(input: {
  isLoading: boolean;
  hasError: boolean;
  hasData: boolean;
}): WorkbenchDataState {
  if (input.isLoading) return "loading";
  if (input.hasError) return "error";
  if (!input.hasData) return "empty";
  return "ready";
}

/** 查询参数读取器。`URLSearchParams` 满足本类型。 */
export type QueryParamReader = {
  get(name: string): string | null;
};

/** 读取 `?q=`。缺省返回空串。 */
export function readQuestionParam(params: QueryParamReader): string {
  const value = params.get("q");
  return value === null ? "" : value;
}

/** 读取 `?project=`。缺省返回空串。 */
export function readProjectParam(params: QueryParamReader): string {
  const value = params.get("project");
  return value === null ? "" : value;
}

/** 任务计数。用于页头的调度摘要。 */
export function summarizeTasks(
  tasks: readonly { status: string }[]
): { total: number; enabled: number } {
  return {
    total: tasks.length,
    enabled: tasks.filter(task => task.status === "enabled").length,
  };
}

/** 右栏门禁说明。顺序与 Playbook 1.3 一致。 */
export const GATE_LEGEND: readonly { id: string; description: string }[] = [
  { id: "G-Plan", description: "确认负责人与停止条件。" },
  { id: "G-Cost", description: "批准成本估算与付费调用。" },
  { id: "G-Evidence", description: "证据等级达到模板阈值。" },
  { id: "G-Claim", description: "主张有证据支撑，反证完整。" },
  { id: "G-Publish", description: "发布前人工批准。" },
];

/** 右栏证据等级图例。取值与 UI 规格 §证据等级一致。 */
export const EVIDENCE_LEGEND: readonly {
  grade: string;
  label: string;
  claim: string;
}[] = [
  { grade: "L0_unverified", label: "L0 · 未核验", claim: "不生成 claim" },
  { grade: "L1_contract", label: "L1 · 合同核验", claim: "不生成 claim" },
  { grade: "L2_fixture_local", label: "L2 · 本地样例", claim: "hypothesis" },
  { grade: "L3_live_single", label: "L3 · 单次真实调用", claim: "directional" },
  { grade: "L4_authorized_live", label: "L4 · 授权真实调用", claim: "confirmed" },
];
