import { API_BASE_URL, ApiError, apiFetch } from "./client";

/**
 * ABI 看板的前端 API 客户端。
 *
 * 契约来源：``apps/api/src/data_intelligence_hub/schemas/abi.py`` 与
 * ``api/routes/abi.py``。安全边界不在本文件：
 * - 隐藏列、PII 遮罩、unknown 列拒绝，全部由 API 序列化层执行。
 * - 列名 allowlist、op 白名单与 SQL 构造由服务端完成，本文件只发结构化过滤。
 * - workspace_id 与 access_grant 由服务端从会话推导，前端不传、不能伪造。
 */

/** ABI 角色。顺序 viewer < editor < publisher < admin。 */
export type AbiRole = "viewer" | "editor" | "publisher" | "admin";

/** 角色等级。admin 不是万能 bypass：没有 grant 时仍然无权访问数据集。 */
export const ABI_ROLE_RANK: Record<AbiRole, number> = {
  viewer: 1,
  editor: 2,
  publisher: 3,
  admin: 4,
};

/** 只做界面提示，不能替代服务端鉴权。 */
export function hasAbiRole(actual: AbiRole | null | undefined, required: AbiRole): boolean {
  if (!actual) return false;
  return ABI_ROLE_RANK[actual] >= ABI_ROLE_RANK[required];
}

/** 目录来源，与 abi.catalog_dataset.source_kind 的 CHECK 约束一致。 */
export type AbiSourceKind = "apify_platform" | "local_table" | "upload";

/** PII 等级，与 abi.field_policy.pii_class 的 CHECK 约束一致。 */
export type AbiPiiClass = "unknown" | "none" | "quasi" | "direct" | "secret";

/** 上传模式，与 abi.upload_batch.mode 的 CHECK 约束一致。 */
export type AbiUploadMode = "append" | "upsert" | "replace";

/** 导出格式，与 abi.export_job.format 的 CHECK 约束一致。 */
export type AbiExportFormat = "csv" | "xlsx" | "jsonl";

/** 查询操作符白名单，与服务端 FilterOperator 一致。 */
export type AbiQueryOp =
  | "eq"
  | "ne"
  | "lt"
  | "lte"
  | "gt"
  | "gte"
  | "in"
  | "contains"
  | "is_null"
  | "not_null";

export const ABI_QUERY_OPS: readonly AbiQueryOp[] = [
  "eq",
  "ne",
  "lt",
  "lte",
  "gt",
  "gte",
  "in",
  "contains",
  "is_null",
  "not_null",
];

export const ABI_QUERY_OP_LABELS: Record<AbiQueryOp, string> = {
  eq: "等于",
  ne: "不等于",
  lt: "小于",
  lte: "小于等于",
  gt: "大于",
  gte: "大于等于",
  in: "属于（逗号分隔）",
  contains: "包含",
  is_null: "为空",
  not_null: "不为空",
};

/** 数据集目录项。字段与 AbiDatasetSummary 对齐。 */
export type AbiDataset = {
  id: string;
  workspace_id: string;
  slug: string;
  name: string;
  description: string | null;
  source_kind: AbiSourceKind;
  source_table: string | null;
  platform: string | null;
  object_type: string | null;
  origin: string | null;
  row_count: number;
  last_loaded_at: string | null;
  version: number;
  is_current: boolean;
  pii_scanned: boolean;
  quality_status: string | null;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
};

/** 物理列。只来自服务端登记表与物理列 allowlist。 */
export type AbiDatasetColumn = {
  id: string;
  column_name: string;
  data_type: string;
  ordinal: number;
  nullable: boolean;
  filterable: boolean;
  sortable: boolean;
};

/** 一个字段的有效 PII 策略。没有策略行时 pii_class 为 unknown。 */
export type AbiPolicyItem = {
  field_path: string;
  pii_class: AbiPiiClass;
  mask_rule: string | null;
  decided_by: string;
  is_default: boolean;
};

export type AbiDatasetDetail = {
  dataset: AbiDataset;
  columns: AbiDatasetColumn[];
  policy: AbiPolicyItem[];
};

/** 目录 keyset 分页响应。cursor 优先于 offset。 */
export type AbiDatasetListResponse = {
  items: AbiDataset[];
  total: number;
  next_cursor: string | null;
  has_more: boolean;
};

/** 工作区总览。只统计当前用户有 grant 的 dataset。 */
export type AbiOverview = {
  dataset_count: number;
  row_count: number;
  pii_pending_datasets: number;
  exports_queued: number;
  exports_running: number;
  exports_succeeded: number;
  uploads_pending: number;
  generated_at: string;
};

export type AbiQueryFilterValue =
  | string
  | number
  | boolean
  | null
  | Array<string | number | boolean>;

export type AbiQueryFilter = {
  column: string;
  op: AbiQueryOp;
  value: AbiQueryFilterValue;
};

export type AbiQueryOrder = {
  column: string;
  direction: "asc" | "desc";
};

export type AbiQueryRequest = {
  /** null 表示由服务端选择所有 PII 已知的列。 */
  columns: string[] | null;
  filters: AbiQueryFilter[];
  order_by: AbiQueryOrder[];
  limit: number;
  offset: number;
};

/** 查询结果。masked_fields 列出本页做过遮罩的列。 */
export type AbiQueryResult = {
  dataset_id: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total: number;
  limit: number;
  offset: number;
  masked_fields: string[];
};

/** 上传批次。字段与 AbiUploadBatchResponse 对齐。 */
export type AbiUploadStatus =
  | "pending"
  | "uploaded"
  | "validating"
  | "committed"
  | "failed"
  | "expired";

export type AbiUploadBatch = {
  id: string;
  dataset_id: string;
  workspace_id: string;
  uploaded_by: string;
  filename: string;
  mode: AbiUploadMode;
  status: AbiUploadStatus;
  bytes_total: number;
  expected_rows: number | null;
  actual_rows: number | null;
  rows_loaded: number;
  rows_rejected: number;
  created_at: string;
  committed_at: string | null;
};

export type AbiUploadCreateRequest = {
  dataset_slug: string;
  filename: string;
  mode: AbiUploadMode;
  expected_sha256: string | null;
  expected_rows: number | null;
};

/** 一次性上传令牌。token 只在创建响应里出现一次。 */
export type AbiUploadCreateResponse = {
  batch: AbiUploadBatch;
  upload_token: string;
  upload_url: string;
  token_expires_at: string;
};

/** 一行校验错误。只有定位与规则名，服务端不回显用户数据。 */
export type AbiUploadErrorItem = {
  row_number: number;
  column_name: string | null;
  rule_id: string;
  message: string | null;
};

export type AbiUploadErrorListResponse = {
  items: AbiUploadErrorItem[];
  total: number;
};

export type AbiUploadListResponse = {
  items: AbiUploadBatch[];
  total: number;
};

export type AbiExportStatus =
  | "queued"
  | "awaiting_approval"
  | "running"
  | "succeeded"
  | "failed"
  | "expired"
  | "rejected";

/** 导出任务。字段与 AbiExportJobResponse 对齐。 */
export type AbiExportJob = {
  id: string;
  workspace_id: string;
  dataset_id: string;
  created_by: string;
  format: AbiExportFormat;
  mask_pii: boolean;
  status: AbiExportStatus;
  filename: string | null;
  content_type: string | null;
  bytes_total: number | null;
  rows_total: number | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  expires_at: string | null;
};

export type AbiExportCreateRequest = {
  dataset_slug: string;
  format: AbiExportFormat;
  mask_pii: boolean;
  columns: string[] | null;
  filters: AbiQueryFilter[];
  order_by: AbiQueryOrder[];
  reason: string | null;
};

/** 授权记录。字段与 AbiGrantResponse 对齐。 */
export type AbiAccessGrant = {
  id: string;
  dataset_id: string;
  workspace_id: string;
  user_id: string;
  role: AbiRole;
  granted_by: string | null;
  created_at: string;
};

export type AbiGrantListResponse = {
  items: AbiAccessGrant[];
  total: number;
};

/** 有效 PII 策略。未知字段以 is_default=true 的 unknown 行返回。 */
export type AbiPolicyResponse = {
  dataset_id: string;
  pii_scanned: boolean;
  items: AbiPolicyItem[];
};

function slugPath(slug: string): string {
  return encodeURIComponent(slug);
}

/** 读取错误响应里的 detail。只用于把服务端文案展示给用户。 */
async function readErrorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail) return body.detail;
  } catch {
    /* 非 JSON 响应按 fallback 处理 */
  }
  return fallback;
}

export async function fetchAbiOverview(): Promise<AbiOverview> {
  return apiFetch<AbiOverview>("/api/abi/overview");
}

export async function fetchAbiDatasets(params?: {
  limit?: number;
  offset?: number;
  cursor?: string | null;
}): Promise<AbiDatasetListResponse> {
  const qs = new URLSearchParams();
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  if (params?.cursor) qs.set("cursor", params.cursor);
  const text = qs.toString();
  return apiFetch<AbiDatasetListResponse>(`/api/abi/datasets${text ? `?${text}` : ""}`);
}

export async function fetchAbiDataset(slug: string): Promise<AbiDatasetDetail> {
  return apiFetch<AbiDatasetDetail>(`/api/abi/datasets/${slugPath(slug)}`);
}

/**
 * 执行结构化查询。
 *
 * 不发送 SQL、表名或任意表达式。columns / filters / order_by 都会在服务端
 * 与服务端物理列 allowlist 和 op 白名单比对；前端选项只用于减少误操作。
 */
export async function queryAbiDataset(
  slug: string,
  payload: AbiQueryRequest,
): Promise<AbiQueryResult> {
  return apiFetch<AbiQueryResult>(`/api/abi/datasets/${slugPath(slug)}/query`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createAbiUpload(
  payload: AbiUploadCreateRequest,
): Promise<AbiUploadCreateResponse> {
  return apiFetch<AbiUploadCreateResponse>("/api/abi/uploads", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * 写上传内容。
 *
 * 必须用裸 fetch：apiFetch 强制 Content-Type: application/json，
 * 会把二进制体变成非法 JSON 请求。X-Upload-Token 是创建批次时下发的一次性令牌。
 * 服务端按令牌定位批次，因此 URL 里不带 batch_id。
 */
export async function uploadAbiContent(
  uploadUrl: string,
  file: File,
  token: string,
): Promise<AbiUploadBatch> {
  const url = uploadUrl.startsWith("http") ? uploadUrl : `${API_BASE_URL}${uploadUrl}`;
  const res = await fetch(url, {
    method: "PUT",
    credentials: "include",
    headers: {
      "Content-Type": "application/octet-stream",
      "X-Upload-Token": token,
    },
    body: file,
  });
  if (!res.ok) {
    const message = await readErrorDetail(res, `上传失败（HTTP ${res.status}）`);
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as AbiUploadBatch;
}

export async function commitAbiUpload(batchId: string): Promise<AbiUploadBatch> {
  return apiFetch<AbiUploadBatch>(
    `/api/abi/uploads/${encodeURIComponent(batchId)}/commit`,
    { method: "POST" },
  );
}

/** 列出某 dataset 的上传批次，按创建时间倒序。 */
export async function listAbiUploads(
  datasetSlug: string,
  options: { limit?: number; offset?: number } = {},
): Promise<AbiUploadListResponse> {
  const params = new URLSearchParams();
  if (options.limit != null) params.set("limit", String(options.limit));
  if (options.offset != null) params.set("offset", String(options.offset));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<AbiUploadListResponse>(
    `/api/abi/datasets/${encodeURIComponent(datasetSlug)}/uploads${suffix}`,
  );
}

/** 批次的行级校验错误。total 是总数，不受 limit 影响。 */
export async function listAbiUploadErrors(
  batchId: string,
  options: { limit?: number; offset?: number } = {},
): Promise<AbiUploadErrorListResponse> {
  const params = new URLSearchParams();
  if (options.limit != null) params.set("limit", String(options.limit));
  if (options.offset != null) params.set("offset", String(options.offset));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<AbiUploadErrorListResponse>(
    `/api/abi/uploads/${encodeURIComponent(batchId)}/errors${suffix}`,
  );
}

/**
 * 重跑 failed 批次的 commit。不需要重新上传字节——
 * 失败发生在 commit 阶段时文件已完整落盘并通过 sha256 校验。
 */
export async function retryAbiUpload(batchId: string): Promise<AbiUploadBatch> {
  return apiFetch<AbiUploadBatch>(
    `/api/abi/uploads/${encodeURIComponent(batchId)}/retry`,
    { method: "POST" },
  );
}

/**
 * 三步上传：建批次 → PUT 内容 → commit。
 *
 * commit 由服务端复核 sha256、行数与表头；任一步失败都不产生可见版本。
 */
export async function uploadAbiBatch(input: {
  datasetSlug: string;
  file: File;
  mode: AbiUploadMode;
  expectedRows?: number | null;
}): Promise<AbiUploadBatch> {
  const created = await createAbiUpload({
    dataset_slug: input.datasetSlug,
    filename: input.file.name,
    mode: input.mode,
    expected_sha256: null,
    expected_rows: input.expectedRows ?? null,
  });
  await uploadAbiContent(created.upload_url, input.file, created.upload_token);
  return commitAbiUpload(created.batch.id);
}

export async function fetchAbiExports(params?: {
  limit?: number;
  offset?: number;
}): Promise<{ items: AbiExportJob[]; total: number }> {
  const qs = new URLSearchParams();
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  const text = qs.toString();
  return apiFetch<{ items: AbiExportJob[]; total: number }>(
    `/api/abi/exports${text ? `?${text}` : ""}`,
  );
}

export async function createAbiExport(
  payload: AbiExportCreateRequest,
): Promise<AbiExportJob> {
  return apiFetch<AbiExportJob>("/api/abi/exports", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getAbiExport(jobId: string): Promise<AbiExportJob> {
  return apiFetch<AbiExportJob>(`/api/abi/exports/${encodeURIComponent(jobId)}`);
}

function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null;
  const utf8 = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1]);
    } catch {
      /* 回退到 ASCII 文件名 */
    }
  }
  const ascii = /filename="?([^";]+)"?/i.exec(header);
  return ascii ? ascii[1] : null;
}

/**
 * 下载导出的二进制体。
 *
 * 服务端按 (job_id, workspace_id, created_by/grant) 取 job，校验过期时间与
 * ``Path.resolve().relative_to(export_root)``；前端只负责把 bytes 交给浏览器。
 */
export async function downloadAbiExport(job: AbiExportJob): Promise<void> {
  if (job.status !== "succeeded") {
    throw new Error("导出尚未完成");
  }
  const res = await fetch(
    `${API_BASE_URL}/api/abi/exports/${encodeURIComponent(job.id)}/download`,
    { credentials: "include" },
  );
  if (!res.ok) {
    const message = await readErrorDetail(res, `下载失败（HTTP ${res.status}）`);
    throw new ApiError(res.status, message);
  }
  const blob = await res.blob();
  const filename =
    filenameFromDisposition(res.headers.get("Content-Disposition")) ??
    job.filename ??
    `abi-export-${job.id}`;
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export async function fetchAbiGrants(slug: string): Promise<AbiGrantListResponse> {
  return apiFetch<AbiGrantListResponse>(`/api/abi/datasets/${slugPath(slug)}/grants`);
}

export async function createAbiGrant(
  slug: string,
  payload: { user_id: string; role: AbiRole },
): Promise<AbiAccessGrant> {
  return apiFetch<AbiAccessGrant>(`/api/abi/datasets/${slugPath(slug)}/grants`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteAbiGrant(
  slug: string,
  grantId: string,
): Promise<{ deleted: boolean; id: string }> {
  return apiFetch<{ deleted: boolean; id: string }>(
    `/api/abi/datasets/${slugPath(slug)}/grants/${encodeURIComponent(grantId)}`,
    { method: "DELETE" },
  );
}

export async function fetchAbiPolicy(slug: string): Promise<AbiPolicyResponse> {
  return apiFetch<AbiPolicyResponse>(`/api/abi/datasets/${slugPath(slug)}/policy`);
}
