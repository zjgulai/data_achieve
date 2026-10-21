/**
 * 能力目录的界面映射。
 *
 * 本模块只做纯函数变换。它不发请求，也不依赖 React。
 * 筛选、分页与三态判定的边界因此可以单测。
 */

import type {
  PublicTool,
  ToolCostSource,
  ToolRiskClass,
} from "./api/tools";

/** 风险类别的展示顺序。 */
export const RISK_CLASS_ORDER: readonly ToolRiskClass[] = [
  "read",
  "generate",
  "outbound",
  "compute",
];

/** 风险类别的中文标签。 */
export const RISK_CLASS_LABELS: Record<ToolRiskClass, string> = {
  read: "只读",
  generate: "生成",
  outbound: "外访",
  compute: "计算",
};

/** 风险类别的一句话释义。 */
export const RISK_CLASS_HINTS: Record<ToolRiskClass, string> = {
  read: "读取公开数据，不产生外部副作用。",
  generate: "生成文本、图片或音频。",
  outbound: "向外部站点或服务发起请求。",
  compute: "在服务端计算或聚合。",
};

/** 徽标的语义色。页面据此选 CSS token。 */
export type Tone = "success" | "info" | "warning" | "muted" | "danger";

/** 风险类别对应的语义色。 */
export const RISK_CLASS_TONES: Record<ToolRiskClass, Tone> = {
  read: "success",
  generate: "info",
  outbound: "warning",
  compute: "muted",
};

/** 取风险类别标签。未知值原样返回。 */
export function riskClassLabel(value: string): string {
  return RISK_CLASS_LABELS[value as ToolRiskClass] ?? value;
}

/** 解析 URL 里的风险类别。非法值返回 null。 */
export function parseRiskClass(
  value: string | null | undefined,
): ToolRiskClass | null {
  if (!value) return null;
  return (RISK_CLASS_ORDER as readonly string[]).includes(value)
    ? (value as ToolRiskClass)
    : null;
}

/**
 * 解析 URL 里的可执行性筛选。
 * `true` 与 `false` 是有效值。其他值与缺省都返回 null。
 */
export function parseExecutableFilter(
  value: string | null | undefined,
): boolean | null {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

/** 解析 URL 里的页码。非法值与越界小值都回到第 1 页。 */
export function parsePage(value: string | null | undefined): number {
  if (!value || !/^\d+$/.test(value)) return 1;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

/** 一页数据。`start` 与 `end` 是 1 起的展示序号。 */
export type PageSlice<T> = {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  start: number;
  end: number;
};

/**
 * 按页切分条目。
 *
 * 页码会被夹到 `[1, totalPages]`。空列表也有 1 页。
 * 这样翻页按钮与计数永远拿到合法值。
 */
export function paginate<T>(
  items: readonly T[],
  page: number,
  pageSize: number,
): PageSlice<T> {
  const size = Number.isFinite(pageSize)
    ? Math.max(1, Math.floor(pageSize))
    : 1;
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / size));
  const requested = Number.isFinite(page) ? Math.floor(page) : 1;
  const current = Math.min(Math.max(1, requested), totalPages);
  const offset = (current - 1) * size;
  const slice = items.slice(offset, offset + size);
  return {
    items: slice,
    page: current,
    pageSize: size,
    total,
    totalPages,
    start: slice.length > 0 ? offset + 1 : 0,
    end: offset + slice.length,
  };
}

/** 列表的四种界面状态。 */
export type ListState = "loading" | "error" | "empty" | "ready";

/**
 * 判定列表状态。加载优先，其次错误，再其次空。
 * 错误只应在没有可用数据时显示。
 */
export function listState(input: {
  isLoading: boolean;
  hasError: boolean;
  itemCount: number;
}): ListState {
  if (input.isLoading) return "loading";
  if (input.hasError) return "error";
  if (input.itemCount === 0) return "empty";
  return "ready";
}

/** 可执行性的界面状态。 */
export type ExecutabilityState =
  | "available"
  | "env_gated"
  | "config_gated"
  | "permanently_blocked"
  | "disabled"
  | "unsupported";

/** 可执行性的展示结果。 */
export type ExecutabilityView = {
  state: ExecutabilityState;
  label: string;
  detail: string;
  tone: Tone;
};

/**
 * 由工具字段判定可执行性。
 *
 * 判定顺序固定。永久拒绝与停用先于缺配置。
 * `executable` 是目录属性。`executable_now` 还含环境因素。
 */
export function executabilityOf(tool: PublicTool): ExecutabilityView {
  const availability = tool.availability.availability;
  if (tool.permanently_blocked) {
    return {
      state: "permanently_blocked",
      label: "永久不可达",
      detail: "策略层无条件拒绝。切换环境也不放行。",
      tone: "muted",
    };
  }
  if (availability === "disabled") {
    return {
      state: "disabled",
      label: "已停用",
      detail: "目录标记为 disabled。",
      tone: "muted",
    };
  }
  const missing = tool.availability.missing_configuration;
  if (missing.length > 0 || availability === "config-gated") {
    return {
      state: "config_gated",
      label: "缺配置",
      detail: missing.length > 0
        ? `缺少：${missing.join("、")}`
        : "目录标记为缺配置。",
      tone: "warning",
    };
  }
  if (!tool.executable) {
    return {
      state: "unsupported",
      label: "目录不可执行",
      detail: "该工具没有登记可执行路径。",
      tone: "muted",
    };
  }
  if (tool.executable_now) {
    return {
      state: "available",
      label: "当前可执行",
      detail: "当前环境允许调用。",
      tone: "success",
    };
  }
  return {
    state: "env_gated",
    label: "环境门控",
    detail: "目录可执行。当前执行环境不放行。",
    tone: "info",
  };
}

const COST_SOURCE_LABELS: Record<ToolCostSource, string> = {
  upstream_estimate: "上游估算",
  platform_price: "平台售价",
  unknown: "来源未知",
};

/** 成本提示的展示结果。 */
export type CostHintView = {
  text: string;
  sourceLabel: string;
  isEstimate: boolean;
  note: string;
};

/**
 * 由成本声明生成展示文本。
 * 上游估算不是平台售价。界面必须保留这条区别。
 */
export function costHintOf(tool: PublicTool): CostHintView {
  const summary = tool.cost.summary?.trim();
  const isEstimate = tool.cost.source === "upstream_estimate";
  return {
    text: summary && summary.length > 0 ? summary : "未登记成本",
    sourceLabel: COST_SOURCE_LABELS[tool.cost.source] ?? tool.cost.source,
    isEstimate,
    note: isEstimate
      ? "上游估算，不是平台售价。"
      : tool.cost.source === "platform_price"
        ? "平台售价。"
        : "成本来源未知。",
  };
}

/** 是否有任一筛选生效。空态文案据此分支。 */
export function hasActiveFilters(filters: {
  query: string;
  riskClass: ToolRiskClass | null;
  executableNow: boolean | null;
}): boolean {
  return (
    filters.query.trim().length > 0 ||
    filters.riskClass !== null ||
    filters.executableNow !== null
  );
}
