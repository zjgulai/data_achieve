export type SuccessfulRunStatus = "success" | "completed";

/** 已结束且不是失败的状态。 */
export type CompletedRunStatus =
  | SuccessfulRunStatus
  | "partial_success"
  | "empty";

export type RunStatusTone =
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "neutral";

export type RunStatusIconName =
  | "check"
  | "alert"
  | "loader"
  | "clock"
  | "inbox";

export type RunStatusMeta = {
  /** 用户可见的中文状态名。 */
  label: string;
  /** 状态的补充说明。没有补充说明时为空串。 */
  description: string;
  /** 语义色。颜色由设计 token 决定。 */
  tone: RunStatusTone;
  /** 图标名。页面把它映射到具体图标组件。 */
  icon: RunStatusIconName;
};

/** 已知状态的状态名、说明、语义色和图标。 */
export const RUN_STATUS_META: Record<string, RunStatusMeta | undefined> = {
  success: {
    label: "成功",
    description: "",
    tone: "success",
    icon: "check",
  },
  completed: {
    label: "已完成",
    description: "",
    tone: "success",
    icon: "check",
  },
  partial_success: {
    label: "部分成功",
    description: "运行结束，但有部分错误。",
    tone: "warning",
    icon: "alert",
  },
  empty: {
    label: "完成但无数据",
    description: "运行完成，但没有取到数据。",
    tone: "warning",
    icon: "inbox",
  },
  failed: {
    label: "失败",
    description: "",
    tone: "danger",
    icon: "alert",
  },
  running: {
    label: "运行中",
    description: "",
    tone: "info",
    icon: "loader",
  },
  pending: {
    label: "等待中",
    description: "",
    tone: "neutral",
    icon: "clock",
  },
};

/**
 * 读取状态元数据。
 * 未识别的状态保留原始字符串，便于发现后端新增状态。
 */
export function runStatusMeta(status: string): RunStatusMeta {
  return (
    RUN_STATUS_META[status] ?? {
      label: status,
      description: "",
      tone: "neutral",
      icon: "clock",
    }
  );
}

/** 状态文字色。 */
export const RUN_STATUS_TEXT_CLASS: Record<RunStatusTone, string> = {
  success: "text-[var(--state-success)]",
  warning: "text-[var(--state-warning)]",
  danger: "text-[var(--state-danger)]",
  info: "text-[var(--state-info)]",
  neutral: "text-[var(--text-tertiary)]",
};

/** 状态卡片的边框和背景。 */
export const RUN_STATUS_CARD_CLASS: Record<RunStatusTone, string> = {
  success: "border-[var(--state-success)] bg-[var(--success-soft)]",
  warning: "border-[var(--state-warning)] bg-[var(--warning-soft)]",
  danger: "border-[var(--state-danger)] bg-[var(--danger-soft)]",
  info: "border-[var(--border-subtle)] bg-[var(--surface-primary)]",
  neutral: "border-[var(--border-subtle)] bg-[var(--surface-primary)]",
};

export function isSuccessfulRunStatus(status: string): status is SuccessfulRunStatus {
  return status === "success" || status === "completed";
}

/**
 * 判断运行是否已结束且没有失败。
 * empty 和 partial_success 都属于已结束状态。
 */
export function isCompletedRunStatus(status: string): status is CompletedRunStatus {
  return (
    isSuccessfulRunStatus(status) ||
    status === "partial_success" ||
    status === "empty"
  );
}
