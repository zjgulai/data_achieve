/**
 * 可达性状态映射。
 *
 * 把后端的可用性与策略字段映射为界面状态。
 * 依据：apps/api/.../collectors/outbound_policy.py 与 platform_packages/status.py。
 *
 * 后端有两组独立信号：
 * 1. 策略阻断。来自 outbound_policy。含执行类别与网络模式。
 * 2. 缺配置。来自 GROUP_REQUIREMENTS。指缺失的环境变量。
 *
 * 两者会同时成立。故界面要分开显示。
 */

/** 界面的可达性状态。 */
export type ReachabilityState =
  | "available"
  | "env_gated"
  | "config_gated"
  | "permanently_blocked"
  | "disabled"
  | "unverified";

/** 一条阻断原因。 */
export type Blocker = {
  kind: "permanent" | "environment" | "configuration" | "catalog";
  /** 界面标题。 */
  title: string;
  /** 原因原文。来自后端。 */
  detail: string;
  /** 处置建议。 */
  action: string;
};

/** 映射的输入。字段可缺省。 */
export type ReachabilityInput = {
  /** 目录的状态字段。 */
  catalogStatus?: string | null;
  /** 目录行的策略阻断原因。 */
  policyBlockReason?: string | null;
  /** 是否永久阻断。来自 /api/tools 的 permanently_blocked。 */
  permanentlyBlocked?: boolean | null;
  /** 缺失的配置项。来自 providers/status 或 /api/tools。 */
  missingConfiguration?: readonly string[] | null;
  /** 当前是否可执行。来自 /api/tools 的 executable_now。 */
  executableNow?: boolean | null;
  /** 可用性枚举。来自 providers/status。 */
  availability?: string | null;
};

/** 映射结果。 */
export type Reachability = {
  state: ReachabilityState;
  /** 界面标签。 */
  label: string;
  /** 全部阻断原因。按后端检查顺序排列。 */
  blockers: Blocker[];
  /** 是否可发起采集。 */
  canRun: boolean;
  /** 是否应显示操作入口。永久不可达时否。 */
  showAction: boolean;
};

/** 原因原文的识别片段。与后端字符串对应。 */
const PERMANENT_MARKERS = ["未具备受控出口"];
const ENVIRONMENT_MARKERS = ["离线模式", "网络模式"];
// 「未获批准」对应 outbound_domain_denied：主机不在批准列表内。
// 它归配置类，但需管理员批准域名，不是用户补密钥能解决的。
const CONFIG_MARKERS = ["域名批准", "批准配置", "未获批准"];

/**
 * 由原因原文判断类型。
 *
 * 结构化字段优先。本函数只在字段缺失时使用。
 */
export function classifyReason(reason: string): Blocker["kind"] {
  if (PERMANENT_MARKERS.some(m => reason.includes(m))) return "permanent";
  if (CONFIG_MARKERS.some(m => reason.includes(m))) return "configuration";
  if (ENVIRONMENT_MARKERS.some(m => reason.includes(m))) return "environment";
  // 未知原因。当作配置类。它需要人工处置。
  return "configuration";
}

/** 构造一条缺配置原因。 */
function configurationBlocker(missing: readonly string[]): Blocker {
  return {
    kind: "configuration",
    title: "需先配置密钥",
    detail: `缺少：${missing.join("、")}`,
    action: "到凭证设置补配置后重试。",
  };
}

/** 构造一条策略原因。 */
function policyBlocker(reason: string): Blocker {
  const kind = classifyReason(reason);
  if (kind === "permanent") {
    return {
      kind,
      title: "该能力永久不可达",
      detail: reason,
      action: "换执行环境也不放行。请改用其他能力。",
    };
  }
  if (kind === "environment") {
    return {
      kind,
      title: "当前执行环境不放行",
      detail: reason,
      action: "换执行环境即可放行。",
    };
  }
  return {
    kind,
    title: "缺少服务端批准",
    detail: reason,
    action: "需服务端配置域名批准。请联系管理员。",
  };
}

/** 状态的界面标签。 */
const STATE_LABELS: Record<ReachabilityState, string> = {
  available: "可执行",
  env_gated: "环境门控",
  config_gated: "缺配置",
  permanently_blocked: "永久不可达",
  disabled: "已停用",
  unverified: "未验证",
};

/** 状态在展示上的先后。序号小的先显示。 */
const STATE_ORDER: ReachabilityState[] = [
  "disabled",
  "permanently_blocked",
  "env_gated",
  "config_gated",
  "unverified",
  "available",
];

/**
 * 求可达性。
 *
 * 阻断原因按后端检查顺序排列：永久、环境、配置。
 * 主状态取第一条原因。这与服务端行为一致。
 */
export function resolveReachability(input: ReachabilityInput): Reachability {
  const blockers: Blocker[] = [];

  // 目录已停用。这是目录状态，不是策略阻断。
  if (input.catalogStatus === "disabled" || input.availability === "disabled") {
    blockers.push({
      kind: "catalog",
      title: "该能力已停用",
      detail: "目录标记为 disabled。",
      action: "不再提供。请改用其他能力。",
    });
  }

  // 原因原文的分类。结构化字段优先于它。
  const reasonKind = input.policyBlockReason
    ? classifyReason(input.policyBlockReason)
    : null;

  // 永久阻断。服务端的第一个检查门。
  const permanent =
    input.permanentlyBlocked === true ||
    input.availability === "unsupported" ||
    reasonKind === "permanent";
  if (permanent && input.catalogStatus !== "disabled") {
    blockers.push({
      kind: "permanent",
      title: "该能力永久不可达",
      detail: input.policyBlockReason ?? "上游实现不受控。",
      action: "换执行环境也不放行。请改用其他能力。",
    });
  }

  // 环境门控。服务端的第二个检查门。
  if (!permanent && reasonKind === "environment") {
    blockers.push(policyBlocker(input.policyBlockReason!));
  }

  // 缺配置。与网络模式独立，可同时成立。
  const missing = input.missingConfiguration ?? [];
  if (missing.length > 0) blockers.push(configurationBlocker(missing));

  // 非永久阻断的策略原因。例如缺域名批准。
  if (!permanent && reasonKind === "configuration" && missing.length === 0) {
    blockers.push(policyBlocker(input.policyBlockReason!));
  }

  // 无阻断原因，但当前不可执行。补一条未说明的环境门。
  // 服务端给了结果却未给原因时走这里。必须放在未验证之前。
  if (blockers.length === 0 && input.executableNow === false) {
    blockers.push({
      kind: "environment",
      title: "当前执行环境不放行",
      detail: "服务端未给出原因。",
      action: "换执行环境即可放行。",
    });
  }

  // 无证据。既不阻断，也未验证。
  if (blockers.length === 0 && input.availability === "untested") {
    blockers.push({
      kind: "catalog",
      title: "尚无实测证据",
      detail: "该能力还没有测试记录。",
      action: "可尝试采集。",
    });
  }

  // 主状态取第一条原因。
  let state: ReachabilityState;
  if (blockers.length === 0) {
    state = "available";
  } else if (blockers[0].kind === "catalog" && input.catalogStatus === "disabled") {
    state = "disabled";
  } else if (blockers[0].kind === "permanent") {
    state = "permanently_blocked";
  } else if (blockers[0].kind === "environment") {
    state = "env_gated";
  } else if (blockers[0].kind === "configuration") {
    state = "config_gated";
  } else {
    state = "unverified";
  }

  // 未验证不算阻断。可尝试。
  const hardBlocked = state !== "available" && state !== "unverified";

  return {
    state,
    label: STATE_LABELS[state],
    blockers,
    canRun: !hardBlocked,
    // 永久不可达与已停用不显示操作入口。
    showAction: state !== "permanently_blocked" && state !== "disabled",
  };
}

/** 取全部状态的展示顺序。 */
export function stateOrder(): readonly ReachabilityState[] {
  return STATE_ORDER;
}

/** 状态对应的颜色变量。 */
export function stateColor(state: ReachabilityState): string {
  switch (state) {
    case "available":
      return "var(--state-success)";
    case "env_gated":
      return "var(--state-warning)";
    case "config_gated":
      return "var(--state-info)";
    case "permanently_blocked":
    case "disabled":
      return "var(--border-strong)";
    default:
      return "var(--text-tertiary)";
  }
}
