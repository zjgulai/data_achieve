/**
 * 报告接口的客户端。
 *
 * 类型对齐 `apps/api/src/data_intelligence_hub/schemas/report_contract.py`。
 * 字段名保持 snake_case。前端不改名，避免与合同漂移。
 * Decimal 在 JSON 中是字符串。这里也写 string。
 */

import { apiFetch } from "./client";
import {
  classifyContract404,
  contractEndpointPath,
  type ArtifactHashes,
  type ClaimView,
  type EvidenceGrade,
  type GateView,
  type WindowView,
} from "../reports-view";

/** `GET /api/reports` 与 `GET /api/reports/{id}` 的响应。 */
export type ReportSummary = {
  id: string;
  workspace_id: string;
  project_id: string | null;
  report_type: string;
  title: string;
  /** 旧版 Markdown 正文。合同生成后不再使用。 */
  content: string;
  status: string;
  period_start: string;
  period_end: string;
  created_at: string;
  delivered_channels: string[];
  skipped_channels: Record<string, string>;
  idempotency_replayed: boolean;
  idempotency_scope: string | null;
  idempotency_key_hash: string | null;
};

/** `identity.family_children[]`。 */
export type FamilyChild = {
  variant_id: string | null;
  sku: string | null;
  asin: string | null;
  color: string | null;
  size: string | null;
};

/** 合同的 `identity` 组。 */
export type Identity = {
  task_id: string;
  brand: string;
  category: string;
  competitors: string[];
  markets: string[];
  window: WindowView;
  product: string | null;
  model: string | null;
  variant_id: string | null;
  sku: string | null;
  asin: string | null;
  parent_asin: string | null;
  bundle: string | null;
  offer: string | null;
  mapping_confidence: number | null;
  family_children: FamilyChild[];
};

/** 合同的 `decision` 组。三个槽位不得省略。 */
export type Decision = {
  decision_question: string;
  answer: string;
  protect: string[];
  resolve: string[];
  prove: string[];
};

/** 合同的 `gates[]`。 */
export type Gate = GateView;

/** 覆盖单元的状态。 */
export type CoverageStatus = "success" | "empty" | "failed";

/** 合同的 `coverage.cells[]`。 */
export type CoverageCell = {
  source_tool_id: string;
  market: string;
  window: WindowView;
  record_count: number;
  frame_member_count: number;
  status: CoverageStatus;
};

/** 合同的 `coverage` 组。只接受对象形状。 */
export type CoverageBlock = {
  cells: CoverageCell[];
};

/** 六种计数口径。来自 PRD 5.5.1。 */
export type CountType =
  | "raw_object"
  | "occurrence"
  | "canonical_record"
  | "frame_member"
  | "annotation"
  | "metric_row";

/** 合同的 `metrics[]`。 */
export type Metric = {
  metric_id: string;
  label: string;
  numerator: number;
  denominator: number;
  count_type: CountType;
  frame: string;
  as_of: string;
  note: string | null;
};

/** claim 的适用范围。 */
export type ClaimScope = ClaimView["scope"];

/** 合同的 `claims[]`。 */
export type Claim = ClaimView;

/** 证据的角色。 */
export type EvidenceRole = "support" | "counter" | "context" | "gap";

/** 合同的 `evidences[]`。 */
export type Evidence = {
  evidence_id: string;
  claim_id: string;
  role: EvidenceRole;
  raw_record_id: string | null;
  source_tool_id: string;
  url: string | null;
  excerpt: string | null;
  captured_at: string;
  market: string;
  locale: string;
  evidence_grade: EvidenceGrade;
};

/** run 的四种结果。来自 `models/run.py` 的 `RunOutcome`。 */
export type RunOutcome = "success" | "empty" | "config_gated" | "failed";

/** 合同的 `run_ledger[]`。 */
export type RunLedgerRow = {
  run_id: string;
  tool_id: string;
  endpoint_type: string;
  actor_id: string | null;
  unit: string;
  quantity: number;
  unit_price: string;
  total_cost_usd: string;
  authorization_id: string | null;
  evidence_grade: EvidenceGrade;
  started_at: string;
  finished_at: string;
  outcome: RunOutcome;
};

/** 合同的 `artifact` 组。三个哈希由调用方写入。 */
export type Artifact = ArtifactHashes;

/** 完整的 `report_contract.json`。 */
export type ReportContract = {
  schema_version: "1.0.0";
  template_id: string;
  generated_at: string;
  identity: Identity;
  decision: Decision;
  gates: Gate[];
  coverage: CoverageBlock;
  metrics: Metric[];
  claims: Claim[];
  evidences: Evidence[];
  run_ledger: RunLedgerRow[];
  limits: string[];
  unknowns: string[];
  artifact: Artifact;
};

/** 列表查询参数。后端当前只支持 `project_id`。 */
export type ReportListQuery = {
  projectId?: string;
};

/**
 * 读取报告列表。
 *
 * 后端只支持 `project_id`。模板、品牌、市场、状态、时间、搜索与分页
 * 都未实现。见 UI 设计 §3.6 的字段缺口。
 */
export async function fetchReports(
  query: ReportListQuery = {},
): Promise<ReportSummary[]> {
  const params = new URLSearchParams();
  if (query.projectId) params.set("project_id", query.projectId);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<ReportSummary[]>(`/api/reports${suffix}`);
}

/** 读取一份报告。不存在或不属于当前工作区时后端返回 404。 */
export async function fetchReportById(reportId: string): Promise<ReportSummary> {
  return apiFetch<ReportSummary>(
    `/api/reports/${encodeURIComponent(reportId)}`,
  );
}

/** 合同读取的三种结果。区分「端点不存在」与「数据未生成」。 */
export type ContractResult =
  | { kind: "ok"; contract: ReportContract }
  /** 端点在，资源不在。 */
  | { kind: "not_generated"; detail: string }
  /** 端点根本没有挂载。 */
  | { kind: "endpoint_missing"; detail: string; endpoint: string };

/** 两种缺口结果。 */
export type ContractGapResult = Exclude<ContractResult, { kind: "ok" }>;

/** 判断合同结果是否是缺口。加载中没有结果时返回 false。 */
export function isContractGapResult(
  result: ContractResult | undefined,
): result is ContractGapResult {
  return result !== undefined && result.kind !== "ok";
}

/**
 * 读取报告合同。
 *
 * 路径来自 UI 设计 §3.7 的 `GET /api/reports/{id}/contract`。
 * 后端目前没有挂载该路由，所以 404 有两种含义，必须分开：
 *
 * - 路由没有挂载：FastAPI 返回 `{"detail": "Not Found"}`。判为
 *   `endpoint_missing`。
 * - 路由已挂载但资源不存在：后端返回业务 detail，例如
 *   `"Report not found"`。判为 `not_generated`。
 * - 两者无法区分时（没有 detail 或 detail 与路由默认值相同），按
 *   `endpoint_missing` 处理。谎报「数据未生成」会让用户以为是自己
 *   数据的问题，比报「端点未实现」更糟。
 *
 * 判断依据写在 `classifyContract404` 的 docstring 里。
 * 非 404 错误原样抛出。
 */
export async function fetchReportContract(
  reportId: string,
): Promise<ContractResult> {
  const endpoint = contractEndpointPath(reportId);
  try {
    const contract = await apiFetch<ReportContract>(endpoint);
    return { kind: "ok", contract };
  } catch (error) {
    if (!isNotFound(error)) throw error;
    const detail = errorDetail(error);
    const kind = classifyContract404(detail);
    if (kind === "endpoint_missing") {
      return { kind, detail, endpoint };
    }
    return { kind, detail };
  }
}

/** 读取错误里的服务端 detail。`ApiError` 把 detail 放在 message 里。 */
function errorDetail(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "";
}

/** 判断错误是否为 404。 */
function isNotFound(error: unknown): boolean {
  if (typeof error !== "object" || error === null) return false;
  if (!("status" in error)) return false;
  return (error as { status?: unknown }).status === 404;
}
