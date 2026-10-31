import {
  ApiRequestError,
  apiFetch,
  apiFetchText,
  mockApiEnabled,
} from "@/lib/api/client";
import type {
  InsightAnalysisType,
  InsightDataScope,
  InsightReportDetail,
  InsightReportSummary,
  InsightReportsPage,
  InsightReportsQuery,
  InsightSourceTable,
} from "@/types/insight";

type InsightAnalysisTypesResponse = {
  items?: unknown;
};

type InsightReportResponse = {
  id?: unknown;
  analysis_type?: unknown;
  title?: unknown;
  summary?: unknown;
  status?: unknown;
  version?: unknown;
  data_scope?: unknown;
  source_status?: unknown;
  source_note?: unknown;
  generated_at?: unknown;
  imported_at?: unknown;
  created_by?: unknown;
  has_content?: unknown;
  content_format?: unknown;
  content_bytes?: unknown;
  content_sha256?: unknown;
};

type InsightReportsResponse = {
  items?: unknown;
  next_cursor?: unknown;
};

const ANALYSIS_TYPE_LABELS: Record<string, string> = {
  tiktok_viral_topic: "TikTok 爆款选题分析",
};

const MOCK_ANALYSIS_TYPES: InsightAnalysisType[] = [
  {
    key: "tiktok_viral_topic",
    name: "TikTok 爆款选题分析",
    description:
      "对已爆母婴与喂养视频做主题、吸引机制、可复刻性和评论需求分析。",
    reportCount: 0,
    latestReportAt: null,
    generation: {
      available: false,
      reasonCode: "mock_mode",
      reason: "本地测试模式不返回示例报告。",
    },
  },
];

export function insightAnalysisTypeLabel(analysisType: string): string {
  if (analysisType.trim().length === 0) {
    return "分析报告";
  }
  return ANALYSIS_TYPE_LABELS[analysisType] ?? analysisType;
}

export async function listInsightAnalysisTypes(): Promise<
  InsightAnalysisType[]
> {
  // mock 模式只返回注册表里的类型，不返回虚构报告。页面据此显示空态，
  // 避免把假数据当成真实分析。
  if (mockApiEnabled) {
    return MOCK_ANALYSIS_TYPES.map((item) => ({
      ...item,
      generation: { ...item.generation },
    }));
  }

  const response = await apiFetch<InsightAnalysisTypesResponse>(
    "/api/insight/analysis-types",
  );
  return readArray(response.items).flatMap((item) => {
    const mapped = mapInsightAnalysisType(item);
    return mapped ? [mapped] : [];
  });
}

export async function listInsightReports(
  input: InsightReportsQuery = {},
): Promise<InsightReportsPage> {
  if (mockApiEnabled) {
    return { items: [], nextCursor: null, mock: true };
  }

  const query = new URLSearchParams();
  if (input.analysisType) {
    query.set("analysis_type", input.analysisType);
  }
  if (input.projectId) {
    query.set("project_id", input.projectId);
  }
  if (typeof input.limit === "number") {
    query.set("limit", String(input.limit));
  }
  if (input.cursor) {
    query.set("cursor", input.cursor);
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";

  const response = await apiFetch<InsightReportsResponse>(
    `/api/insight/reports${suffix}`,
  );
  return {
    items: readArray(response.items).flatMap((item) => {
      const mapped = mapInsightReport(item);
      return mapped ? [mapped] : [];
    }),
    nextCursor: readNullableString(response.next_cursor),
    mock: false,
  };
}

export async function getInsightReport(
  reportId: string,
): Promise<InsightReportDetail> {
  if (mockApiEnabled) {
    // 详情页在 mock 模式下直接显示空态，不会调用这里。保留 fail-closed
    // 的兜底，避免其他调用方把 mock 当成真实报告。
    throw new ApiRequestError(404, "本地测试模式没有归档报告", {
      code: "insight_report_not_found",
    });
  }

  const response = await apiFetch<InsightReportResponse>(
    `/api/insight/reports/${encodeURIComponent(reportId)}`,
  );
  const report = mapInsightReport(response);
  if (!report) {
    throw new ApiRequestError(502, "报告元数据格式无效", {
      code: "internal_server_error",
    });
  }
  return report;
}

export async function getInsightReportContent(
  reportId: string,
): Promise<string> {
  if (mockApiEnabled) {
    throw new ApiRequestError(409, "本地测试模式没有归档报告", {
      code: "insight_report_content_missing",
    });
  }

  return apiFetchText(
    `/api/insight/reports/${encodeURIComponent(reportId)}/content`,
  );
}

/**
 * 下载正文。`?download=1` 让服务端返回 attachment，但前端仍用认证
 * fetch 读取字节再触发 Blob 下载：API 与 Web 可能跨站，直接打开链接
 * 会受 Cookie SameSite 限制。
 */
export async function downloadInsightReportContent(
  reportId: string,
  filename: string,
): Promise<void> {
  if (mockApiEnabled) {
    throw new ApiRequestError(409, "本地测试模式没有归档报告", {
      code: "insight_report_content_missing",
    });
  }

  const html = await apiFetchText(
    `/api/insight/reports/${encodeURIComponent(reportId)}/content?download=1`,
  );
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
  }
}

export function insightReportDownloadFilename(
  report: Pick<InsightReportSummary, "analysisType" | "version" | "id">,
): string {
  const type = report.analysisType.trim().replaceAll("_", "-");
  const version = report.version.trim();
  if (type && version) {
    return `${type}-${version}.html`;
  }
  return `insight-report-${report.id}.html`;
}

export type InsightErrorContext = "types" | "list" | "detail" | "content";

export type InsightErrorKind =
  | "auth"
  | "workspace"
  | "not_found"
  | "content_missing"
  | "integrity_failed"
  | "validation"
  | "unavailable";

export type InsightErrorDescription = {
  kind: InsightErrorKind;
  title: string;
  detail: string;
};

/**
 * 把 API 错误翻译成页面文案。
 *
 * 数据源状态、正文缺失、完整性失败、网络错误、登录过期、工作区不可用
 * 必须是不同的话。不要合并成一句“加载失败”。
 */
export function describeInsightError(
  error: unknown,
  context: InsightErrorContext,
): InsightErrorDescription {
  const status = error instanceof ApiRequestError ? error.status : null;
  const code = error instanceof ApiRequestError ? error.code : null;

  if (status === 401 || code === "authentication_required") {
    return {
      kind: "auth",
      title: "登录已过期，请重新登录。",
      detail: "登录后可以继续查看归档报告。",
    };
  }

  if (status === 403 || code === "workspace_not_found") {
    return {
      kind: "workspace",
      title: "当前工作区不可用。",
      detail: "请切换工作区或联系管理员。",
    };
  }

  if (code === "insight_report_content_missing") {
    return {
      kind: "content_missing",
      title: "报告正文未导入。",
      detail: "报告的元数据已入库，正文记录不存在或未写入。",
    };
  }

  if (code === "insight_report_integrity_failed") {
    return {
      kind: "integrity_failed",
      title: "报告正文校验失败。",
      detail: "正文的 SHA-256 与入库记录不一致。系统已停止展示，避免显示被改动的报告。",
    };
  }

  if (
    code === "insight_report_not_found" ||
    (status === 404 && (context === "detail" || context === "content"))
  ) {
    return {
      kind: "not_found",
      title: "报告不存在或已被移除。",
      detail: "请返回列表，确认报告是否仍然可用。",
    };
  }

  if (status === 422 || code === "validation_error") {
    return {
      kind: "validation",
      title: "请求参数无效。",
      detail: "请刷新页面后重试。",
    };
  }

  if (context === "detail") {
    return {
      kind: "unavailable",
      title: "无法加载报告。",
      detail: "网络或服务异常，请稍后重试。",
    };
  }

  if (context === "content") {
    return {
      kind: "unavailable",
      title: "无法加载报告正文。",
      detail: "网络或服务异常，请稍后重试。",
    };
  }

  return {
    kind: "unavailable",
    title: "无法连接服务器。",
    detail: "报告列表没有加载。",
  };
}

export function mapInsightAnalysisType(
  value: unknown,
): InsightAnalysisType | null {
  const record = asRecord(value);
  const key = readString(record.key);
  if (!key) {
    return null;
  }
  const generation = asRecord(record.generation);
  const reportCount = readNumber(record.report_count);
  return {
    key,
    name: readString(record.name, key),
    description: readString(record.description),
    reportCount: reportCount > 0 ? Math.floor(reportCount) : 0,
    latestReportAt: readNullableString(record.latest_report_at),
    generation: {
      available: generation.available === true,
      reasonCode: readString(generation.reason_code, "source_not_connected"),
      reason: readString(generation.reason),
    },
  };
}

export function mapInsightReport(value: unknown): InsightReportSummary | null {
  const record = asRecord(value);
  const id = readString(record.id);
  if (!id) {
    return null;
  }

  const contentBytes =
    typeof record.content_bytes === "number" &&
    Number.isFinite(record.content_bytes)
      ? Math.max(0, Math.floor(record.content_bytes))
      : null;
  const contentSha256 = readNullableString(record.content_sha256);
  const contentFormat =
    readString(record.content_format) === "html" ? "html" : null;

  return {
    id,
    analysisType: readString(record.analysis_type),
    title: readString(record.title),
    summary: readString(record.summary),
    status: readString(record.status, "ready"),
    version: readString(record.version),
    dataScope: mapInsightDataScope(record.data_scope),
    sourceStatus: readString(record.source_status, "snapshot_only"),
    sourceNote: readNullableString(record.source_note),
    generatedAt: readString(record.generated_at),
    importedAt: readString(record.imported_at),
    createdBy: readNullableString(record.created_by),
    hasContent: record.has_content === true && contentSha256 !== null,
    contentFormat,
    contentBytes,
    contentSha256,
  };
}

export function mapInsightDataScope(value: unknown): InsightDataScope {
  const record = asRecord(value);
  const source = asRecord(record.source);
  return {
    windowLabel: readString(record.window_label),
    windowEnd: readString(record.window_end),
    sampleSize: Math.max(0, Math.floor(readNumber(record.sample_size))),
    sampling: readString(record.sampling),
    source: {
      environment: readString(source.environment),
      database: readString(source.database),
      lastWriteAt: readString(source.last_write_at),
      tables: readArray(source.tables).flatMap((item) => {
        const table = asRecord(item);
        const name = readString(table.name);
        if (!name) {
          return [];
        }
        const mapped: InsightSourceTable = {
          schema: readString(table.schema, readString(table.schema_name)),
          name,
          rows: Math.max(0, Math.floor(readNumber(table.rows))),
        };
        return [mapped];
      }),
    },
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function readArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function readString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function readNullableString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function readNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
