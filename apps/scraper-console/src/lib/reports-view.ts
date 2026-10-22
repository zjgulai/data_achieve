/**
 * 报告页的纯显示逻辑。
 *
 * 本模块不依赖 React，也不发请求。可以单测。
 * 证据等级与 claim 状态的取值来自
 * `apps/api/src/data_intelligence_hub/schemas/report_contract.py`。
 * 文案与颜色只在本模块定义。页面不得另写一份。
 */

/** 五个证据等级。来自 PRD 5.4.2。 */
export type EvidenceGrade =
  | "L0_unverified"
  | "L1_contract"
  | "L2_fixture_local"
  | "L3_live_single"
  | "L4_authorized_live";

/** claim 的五个状态。来自契约冻结 v1 §2.6。 */
export type ClaimStatus =
  | "confirmed"
  | "directional"
  | "hypothesis"
  | "evidence_gap"
  | "blocked";

/** 门禁的五个状态。来自契约冻结 v1 §2.7。 */
export type GateStatus = "pending" | "pass" | "fail" | "blocked" | "expired";

/** 视觉色调。颜色由页面的设计 token 决定。 */
export type StatusTone = "success" | "warning" | "neutral" | "danger";

/** 等级从低到高。数值越小，等级越低。 */
export const EVIDENCE_GRADE_ORDER: Record<EvidenceGrade, number> = {
  L0_unverified: 0,
  L1_contract: 1,
  L2_fixture_local: 2,
  L3_live_single: 3,
  L4_authorized_live: 4,
};

/** 等级的低到高顺序。 */
export const EVIDENCE_GRADES: readonly EvidenceGrade[] = [
  "L0_unverified",
  "L1_contract",
  "L2_fixture_local",
  "L3_live_single",
  "L4_authorized_live",
];

/** 等级的中文全称。 */
export const EVIDENCE_GRADE_LABELS: Record<EvidenceGrade, string> = {
  L0_unverified: "未验证",
  L1_contract: "合同已校验",
  L2_fixture_local: "夹具回放",
  L3_live_single: "方向性",
  L4_authorized_live: "已确认",
};

/** 等级徽章的短文案。含等级代号与全称。 */
export const EVIDENCE_GRADE_BADGE_LABELS: Record<EvidenceGrade, string> = {
  L0_unverified: "L0 · 未实测",
  L1_contract: "L1 · 契约已校验",
  L2_fixture_local: "L2 · 夹具回放",
  L3_live_single: "L3 · 单次真实调用",
  L4_authorized_live: "L4 · 授权真实调用",
};

/** 等级的语义色。 */
export const EVIDENCE_GRADE_TONES: Record<EvidenceGrade, StatusTone> = {
  L0_unverified: "danger",
  L1_contract: "neutral",
  L2_fixture_local: "neutral",
  L3_live_single: "warning",
  L4_authorized_live: "success",
};

/** claim 状态的低到高顺序。用于固定分布顺序。 */
export const CLAIM_STATUSES: readonly ClaimStatus[] = [
  "confirmed",
  "directional",
  "hypothesis",
  "evidence_gap",
  "blocked",
];

/** claim 状态的中文标签。 */
export const CLAIM_STATUS_LABELS: Record<ClaimStatus, string> = {
  confirmed: "已确认",
  directional: "方向性",
  hypothesis: "假设",
  evidence_gap: "证据缺口",
  blocked: "门禁阻断",
};

/** claim 状态的语义色。 */
export const CLAIM_STATUS_TONES: Record<ClaimStatus, StatusTone> = {
  confirmed: "success",
  directional: "warning",
  hypothesis: "neutral",
  evidence_gap: "warning",
  blocked: "danger",
};

/** 门禁状态的英文标签。首屏使用。 */
export const GATE_STATUS_LABELS: Record<GateStatus, string> = {
  pending: "PENDING",
  pass: "PASS",
  fail: "FAIL",
  blocked: "BLOCKED",
  expired: "授权已过期，门禁失效",
};

/** 门禁状态的语义色。 */
export const GATE_STATUS_TONES: Record<GateStatus, StatusTone> = {
  pending: "warning",
  pass: "success",
  fail: "danger",
  blocked: "danger",
  expired: "warning",
};

/**
 * 低于 L4 时禁止出现在 claim 文案里的三个词。
 *
 * 来源是 PRD 5.4.2 与 `report_contract.BELOW_L4_FORBIDDEN_WORDS`。
 * 页面只用本常量。不得另写一份。
 */
export const BELOW_L4_FORBIDDEN_WORDS: readonly string[] = [
  "确认",
  "证明",
  "必然",
];

/** L4 的顺序值。 */
export const L4_ORDER = EVIDENCE_GRADE_ORDER.L4_authorized_live;

/** 合同里的时间窗。日期是 `YYYY-MM-DD`。 */
export type WindowView = {
  start: string;
  end: string;
  days: number;
};

/** claim 的显示形状。字段与 `report_contract.Claim` 一致。 */
export type ClaimView = {
  claim_id: string;
  text: string;
  claim_status: ClaimStatus;
  evidence_grade: EvidenceGrade;
  scope: {
    market: string;
    window: WindowView;
    sample_n: number;
  };
  counterevidence_text: string;
  owner: string;
  evidence_ids: string[];
};

/** 门禁的显示形状。字段与 `report_contract.Gate` 一致。 */
export type GateView = {
  gate_id: string;
  status: GateStatus;
  owner?: string | null;
  decided_at?: string | null;
  note?: string | null;
};

/** 合同 `artifact` 组的三个哈希。 */
export type ArtifactHashes = {
  report_html_sha256: string;
  sop_html_sha256: string;
  contract_sha256: string;
};

/** 合同接口的路径。参数是报告 ID。 */
export function contractEndpointPath(reportId: string): string {
  return `/api/reports/${encodeURIComponent(reportId)}/contract`;
}

/** 合同 404 的两种语义。 */
export type ContractGapKind = "not_generated" | "endpoint_missing";

/** FastAPI 对未挂载路由返回的 detail 固定值。 */
export const ROUTE_NOT_FOUND_DETAIL = "Not Found";

/** `apiFetch` 在响应没有 detail 时生成的兜底消息前缀。 */
const API_ERROR_MESSAGE_PREFIX = "API error ";

/**
 * 判定合同接口 404 的语义。
 *
 * 判断依据是 FastAPI 的默认行为：
 * - 路由没有挂载时，Starlette 返回 `{"detail": "Not Found"}`。
 *   detail 是纯字符串，与业务文案不同。
 * - 路由已挂载但资源不存在时，业务代码抛 HTTPException，
 *   detail 是业务文案。后端报告路由实际返回 `"Report not found"`。
 *
 * 无法可靠区分时按 `endpoint_missing` 处理。没有 detail 或 detail
 * 与路由默认值相同时都属于这种情况。谎报「数据未生成」会让用户
 * 以为是自己数据的问题，比报「端点未实现」更糟。
 */
export function classifyContract404(
  detail: string | null | undefined,
): ContractGapKind {
  const text = detail?.trim() ?? "";
  if (!text) return "endpoint_missing";
  if (text === ROUTE_NOT_FOUND_DETAIL) return "endpoint_missing";
  // 客户端没有读到 detail 时只能猜。按端点缺失处理。
  if (text.startsWith(API_ERROR_MESSAGE_PREFIX)) return "endpoint_missing";
  return "not_generated";
}

/**
 * 无合同时的短文案。
 *
 * 必须区分「数据未生成」与「接口未实现」。页面不得把后者写成前者。
 */
export function contractAbsenceText(kind: ContractGapKind): string {
  if (kind === "endpoint_missing") return "合同接口未提供";
  return "本合同尚未生成";
}

/** 合同缺口的展示模型。页面按本模型渲染。 */
export type ContractGapView = {
  kind: ContractGapKind;
  title: string;
  hint: string;
  role: "alert" | "status";
  retryable: boolean;
};

/** 合同首屏的三种渲染分支。 */
export type ContractRenderBranch =
  | "contract"
  | "not_generated"
  | "endpoint_missing";

/**
 * 取合同首屏的渲染分支。
 *
 * `contract` 渲染合同正文。两个缺口各渲染自己的提示。
 * 没有结果时返回 null，页面显示加载中。
 */
export function contractRenderBranch(
  result: { kind: "ok" | ContractGapKind } | undefined,
): ContractRenderBranch | null {
  if (!result) return null;
  if (result.kind === "ok") return "contract";
  return result.kind;
}

/**
 * 生成合同缺口的展示模型。
 *
 * `endpoint_missing` 用 `role="alert"`，并列出缺失的端点。
 * 用户必须能看出这是接口缺口，不是自己的数据问题。
 * 重试对端点缺失没有意义，所以 `retryable` 是 false。
 */
export function contractGapView(input: {
  kind: ContractGapKind;
  endpoint: string;
}): ContractGapView {
  if (input.kind === "endpoint_missing") {
    return {
      kind: "endpoint_missing",
      title: "报告合同接口尚未提供",
      hint: `后端没有挂载 GET ${input.endpoint}。这不表示报告数据缺失。`,
      role: "alert",
      retryable: false,
    };
  }
  return {
    kind: "not_generated",
    title: "本合同尚未生成",
    hint: "报告存在，但合同还没有生成。可以重试读取。",
    role: "status",
    retryable: true,
  };
}

/** 报告列表在无合同时的占位文案。不得写成「未生成」。 */
export const LIST_CONTRACT_PENDING_LABEL = "待合同接口";

/** 五模板的显示名。模板 ID 来自 B2 阈值表。 */
const TEMPLATE_LABELS: Record<string, string> = {
  t1_voc: "T1 VOC",
  t2_competitor: "T2 竞品",
  t3_selection: "T3 选品",
  t4_creator: "T4 达人",
  t5_compliance: "T5 合规",
};

/** 判断一个值是否是合法证据等级。 */
export function isEvidenceGrade(value: unknown): value is EvidenceGrade {
  return typeof value === "string" && value in EVIDENCE_GRADE_ORDER;
}

/** 判断等级是否低于 L4。未知等级按低于 L4 处理。 */
export function isBelowL4(grade: EvidenceGrade | null | undefined): boolean {
  if (!grade) return true;
  const order = EVIDENCE_GRADE_ORDER[grade];
  if (order === undefined) return true;
  return order < L4_ORDER;
}

/**
 * 求本次报告的最低证据等级。
 *
 * 规则来自 UI 设计 §3.6：取 `claims[].evidence_grade` 的最小值。
 * 没有 claim 时返回 null。页面显示「无 claim」，不猜等级。
 */
export function lowestEvidenceGrade(
  claims: readonly { evidence_grade: EvidenceGrade }[],
): EvidenceGrade | null {
  let lowest: EvidenceGrade | null = null;
  for (const claim of claims) {
    if (
      lowest === null ||
      EVIDENCE_GRADE_ORDER[claim.evidence_grade] <
        EVIDENCE_GRADE_ORDER[lowest]
    ) {
      lowest = claim.evidence_grade;
    }
  }
  return lowest;
}

/** claim 分布的一行。零值也保留。 */
export type ClaimDistributionRow = {
  status: ClaimStatus;
  label: string;
  count: number;
};

/**
 * 统计 claim 状态分布。
 *
 * 五个状态按固定顺序返回。零值也返回。
 * UI 设计 §6.2 要求首屏显示零值。
 * `evidence_gap` 的短标签是 `gap`，与 PRD 7.3.1 的示例一致。
 */
export function claimDistribution(
  claims: readonly { claim_status: ClaimStatus }[],
): ClaimDistributionRow[] {
  const counts = new Map<ClaimStatus, number>();
  for (const claim of claims) {
    counts.set(claim.claim_status, (counts.get(claim.claim_status) ?? 0) + 1);
  }
  return CLAIM_STATUSES.map(status => ({
    status,
    label: status === "evidence_gap" ? "gap" : status,
    count: counts.get(status) ?? 0,
  }));
}

/** 首屏的 claim 分布文案。 */
export function claimDistributionText(
  claims: readonly { claim_status: ClaimStatus }[],
): string {
  return claimDistribution(claims)
    .map(row => `${row.label} ${row.count}`)
    .join(" · ");
}

/**
 * 找出低于 L4 的 claim 文案里的禁用词。
 *
 * 等级达到 L4 时返回空数组。
 * 未知等级按低于 L4 处理。
 */
export function findForbiddenWords(
  text: string,
  grade: EvidenceGrade | null | undefined,
): string[] {
  if (!isBelowL4(grade)) return [];
  return BELOW_L4_FORBIDDEN_WORDS.filter(word => text.includes(word));
}

/** claim 状态徽章的文案。附带降级标记。 */
export type ClaimStatusDisplay = {
  label: string;
  downgraded: boolean;
  tone: StatusTone;
};

/**
 * 取 claim 状态徽章的文案。
 *
 * 等级低于 L4 时，`confirmed` 不得显示为「已确认」。
 * 这种情况显示「状态越级」，并保留警示色。
 * 其他状态只按枚举显示。等级本身由等级徽章显示。
 */
export function claimStatusDisplay(
  status: ClaimStatus,
  grade: EvidenceGrade | null | undefined,
): ClaimStatusDisplay {
  if (status === "confirmed" && isBelowL4(grade)) {
    return { label: "状态越级", downgraded: true, tone: "danger" };
  }
  return {
    label: CLAIM_STATUS_LABELS[status] ?? status,
    downgraded: false,
    tone: CLAIM_STATUS_TONES[status] ?? "neutral",
  };
}

/** 等级徽章的文案。等级缺失时显示「未生成」。 */
export function gradeBadgeText(grade: EvidenceGrade | null | undefined): string {
  if (!grade) return "未生成";
  if (!isEvidenceGrade(grade)) return String(grade);
  return EVIDENCE_GRADE_BADGE_LABELS[grade];
}

/** 门禁状态的中文或英文标签。 */
export function gateStatusLabel(status: GateStatus): string {
  return GATE_STATUS_LABELS[status] ?? status;
}

/** 证据角色的显示名。 */
export const EVIDENCE_ROLE_LABELS: Record<string, string> = {
  support: "支持",
  counter: "反证",
  context: "背景",
  gap: "缺口",
};

/** 取证据角色的显示名。未知角色原样返回。 */
export function evidenceRoleLabel(role: string): string {
  return EVIDENCE_ROLE_LABELS[role] ?? role;
}

/**
 * 判断链接能否放进 `href`。
 *
 * 只允许 http、https 与站内相对地址。
 * 拒绝 `javascript:` 与 `//host` 一类协议相对地址。
 * 规则与服务端渲染器一致。
 */
export function isSafeLink(url: string | null | undefined): boolean {
  if (!url) return false;
  const text = url.trim();
  if (text.startsWith("//")) return false;
  return (
    text.startsWith("http://") ||
    text.startsWith("https://") ||
    text.startsWith("/")
  );
}

/**
 * 选择首屏显示的门禁。
 *
 * 优先选 G-Publish。没有时选第一条。
 * 没有门禁时返回 null。页面显示合同缺口语义文案。
 */
export function selectGate(
  gates: readonly GateView[],
  preferredId = "G-Publish",
): GateView | null {
  return gates.find(gate => gate.gate_id === preferredId) ?? gates[0] ?? null;
}

/** 首屏的门禁文案。例如「G-Publish PASS」。 */
export function gateLine(gates: readonly GateView[]): string | null {
  const gate = selectGate(gates);
  if (!gate) return null;
  return `${gate.gate_id} ${gateStatusLabel(gate.status)}`;
}

/** 模板 ID 的显示名。未知模板原样返回。 */
export function templateLabel(templateId: string | null | undefined): string {
  if (!templateId) return "未生成合同";
  return TEMPLATE_LABELS[templateId] ?? templateId;
}

/** 三个哈希的键。 */
export type ReportHashKey = "contract" | "data" | "render";

/** 一行哈希的取值状态。 */
export type ReportHashStatus = "present" | "not_generated" | "endpoint_missing";

/** 一行哈希展示。 */
export type ReportHashRow = {
  key: ReportHashKey;
  label: string;
  value: string | null;
  /** 缺失时的原因。有值时是 `present`。 */
  status: ReportHashStatus;
  display: string;
};

/** 缺失值的两种文案。不得混用。 */
export const HASH_NOT_GENERATED_LABEL = "未生成";
export const HASH_ENDPOINT_MISSING_LABEL = "接口未提供";

const REPORT_HASH_LABELS: Record<ReportHashKey, string> = {
  contract: "合同哈希",
  data: "数据哈希",
  render: "渲染哈希",
};

const REPORT_HASH_ORDER: readonly ReportHashKey[] = [
  "contract",
  "data",
  "render",
];

/**
 * 生成首屏的三行哈希。
 *
 * 合同哈希与渲染哈希取自合同的 `artifact` 组。
 * 数据哈希来自产物记录。
 *
 * 缺失原因分两种，文案不同：
 * - 接口没有挂载时显示「接口未提供」。当前后端没有产物端点，
 *   所以 `dataEndpointAvailable` 的默认值是 false。
 * - 接口可用但数据没有生成时显示「未生成」。
 *
 * 页面不得补造哈希。
 */
export function reportHashRows(input: {
  contract: { artifact?: ArtifactHashes | null } | null;
  dataSha256?: string | null;
  /** 合同接口是否可用。false 时合同哈希与渲染哈希显示「接口未提供」。 */
  contractEndpointAvailable?: boolean;
  /** 产物接口是否可用。当前后端没有该接口，默认 false。 */
  dataEndpointAvailable?: boolean;
}): ReportHashRow[] {
  const contractEndpointAvailable = input.contractEndpointAvailable ?? true;
  const dataEndpointAvailable = input.dataEndpointAvailable ?? false;
  const artifact = input.contract?.artifact ?? null;
  const values: Record<ReportHashKey, string | null> = {
    contract: cleanDigest(artifact?.contract_sha256),
    data: cleanDigest(input.dataSha256),
    render: cleanDigest(artifact?.report_html_sha256),
  };
  const available: Record<ReportHashKey, boolean> = {
    contract: contractEndpointAvailable,
    data: dataEndpointAvailable,
    render: contractEndpointAvailable,
  };
  return REPORT_HASH_ORDER.map(key => {
    const value = values[key];
    const status: ReportHashStatus = value
      ? "present"
      : available[key]
        ? "not_generated"
        : "endpoint_missing";
    return {
      key,
      label: REPORT_HASH_LABELS[key],
      value,
      status,
      display:
        value ??
        (status === "endpoint_missing"
          ? HASH_ENDPOINT_MISSING_LABEL
          : HASH_NOT_GENERATED_LABEL),
    };
  });
}

/** 去掉空白。空串按缺失处理。 */
function cleanDigest(value: string | null | undefined): string | null {
  const text = value?.trim();
  return text ? text : null;
}

/** 列表页的五种状态。 */
export type ReportListState =
  | "loading"
  | "ready"
  | "empty"
  | "forbidden"
  | "error";

/** 从错误对象读 HTTP 状态码。没有时返回 null。 */
function errorStatus(error: unknown): number | null {
  if (typeof error !== "object" || error === null) return null;
  if (!("status" in error)) return null;
  const value = (error as { status?: unknown }).status;
  return typeof value === "number" ? value : null;
}

/**
 * 判定列表页的状态。
 *
 * 401 与 403 归为「无权限」。其他错误归为「加载失败」。
 * 三种空态文案不同。规则来自 UI 设计 §3.6。
 */
export function resolveReportListState(input: {
  isLoading: boolean;
  error: unknown;
  count: number | undefined;
}): ReportListState {
  if (input.isLoading) return "loading";
  if (input.error) {
    const status = errorStatus(input.error);
    return status === 401 || status === 403 ? "forbidden" : "error";
  }
  if ((input.count ?? 0) === 0) return "empty";
  return "ready";
}

/** 阅读页的四种状态。 */
export type ReportDetailState = "loading" | "empty" | "error" | "ready";

/**
 * 判定阅读页的状态。
 *
 * 404 归为「报告不存在」。其他错误归为「加载失败」。
 */
export function resolveReportDetailState(input: {
  isLoading: boolean;
  error: unknown;
  report: unknown | null | undefined;
}): ReportDetailState {
  if (input.isLoading) return "loading";
  if (input.error) {
    return errorStatus(input.error) === 404 ? "empty" : "error";
  }
  return input.report ? "ready" : "empty";
}

/** 格式化时间。非法值显示破折号。 */
export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("zh-CN", { hour12: false });
}

/** 格式化报告周期。 */
export function formatPeriod(
  start: string | null | undefined,
  end: string | null | undefined,
): string {
  return `${formatTimestamp(start)} — ${formatTimestamp(end)}`;
}

/** 哈希的折叠摘要文案。区分两种缺失原因。 */
export function hashSummaryLabel(rows: readonly ReportHashRow[]): string {
  const missing = rows.filter(row => row.value === null);
  if (missing.length === 0) return "三个哈希";
  const unavailable = missing.filter(
    row => row.status === "endpoint_missing",
  ).length;
  const notGenerated = missing.length - unavailable;
  if (unavailable === rows.length) return "三个哈希接口未提供";
  if (notGenerated === rows.length) return "三个哈希未生成";
  return `三个哈希（${notGenerated} 项未生成，${unavailable} 项接口未提供）`;
}
