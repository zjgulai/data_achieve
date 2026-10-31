import { describe, expect, it } from "vitest";

import { ApiRequestError } from "@/lib/api/client";
import {
  describeInsightError,
  insightAnalysisTypeLabel,
  insightReportDownloadFilename,
  mapInsightAnalysisType,
  mapInsightReport,
} from "@/lib/api/insight";

const reportResponse = {
  id: "report-a",
  analysis_type: "tiktok_viral_topic",
  title: "下周拍什么",
  summary: "优先拍常青内容。",
  status: "ready",
  version: "2026-10-31",
  data_scope: {
    window_label: "2026-10",
    window_end: "2026-10-28",
    sample_size: 288,
    sampling: "392 个 hashtag × 43 天",
    source: {
      environment: "local docker / abi_migtest",
      database: "abitest",
      last_write_at: "2026-10-28",
      tables: [
        { schema: "raw", name: "si_tiktok_video", rows: 31366 },
        { schema: "raw", name: "si_tiktok_comment", rows: 47073 },
      ],
    },
  },
  source_status: "snapshot_only",
  source_note: "报告基于本地快照生成。",
  generated_at: "2026-10-31T00:00:00Z",
  imported_at: "2026-10-31T10:00:00Z",
  created_by: null,
  has_content: true,
  content_format: "html",
  content_bytes: 181984,
  content_sha256: "f".repeat(64),
};

describe("insight report mapping", () => {
  it("maps snake_case metadata and data_scope without touching content", () => {
    const report = mapInsightReport(reportResponse);

    expect(report).toMatchObject({
      id: "report-a",
      analysisType: "tiktok_viral_topic",
      status: "ready",
      version: "2026-10-31",
      sourceStatus: "snapshot_only",
      sourceNote: "报告基于本地快照生成。",
      hasContent: true,
      contentFormat: "html",
      contentBytes: 181984,
    });
    expect(report?.dataScope).toMatchObject({
      windowLabel: "2026-10",
      windowEnd: "2026-10-28",
      sampleSize: 288,
      sampling: "392 个 hashtag × 43 天",
    });
    expect(report?.dataScope.source.tables).toEqual([
      { schema: "raw", name: "si_tiktok_video", rows: 31366 },
      { schema: "raw", name: "si_tiktok_comment", rows: 47073 },
    ]);
  });

  it("fails closed when content metadata is missing", () => {
    const report = mapInsightReport({
      ...reportResponse,
      has_content: false,
      content_format: null,
      content_bytes: null,
      content_sha256: null,
    });

    expect(report?.hasContent).toBe(false);
    expect(report?.contentFormat).toBeNull();
    expect(report?.contentBytes).toBeNull();
    expect(report?.contentSha256).toBeNull();
  });

  it("accepts schema_name as a fallback for table schema", () => {
    const report = mapInsightReport({
      ...reportResponse,
      data_scope: {
        ...reportResponse.data_scope,
        source: {
          ...reportResponse.data_scope.source,
          tables: [{ schema_name: "raw", name: "si_tiktok_video", rows: 1 }],
        },
      },
    });

    expect(report?.dataScope.source.tables[0]).toEqual({
      schema: "raw",
      name: "si_tiktok_video",
      rows: 1,
    });
  });

  it("drops malformed rows instead of inventing reports", () => {
    expect(mapInsightReport({ title: "no id" })).toBeNull();
    expect(mapInsightAnalysisType({ name: "no key" })).toBeNull();
  });

  it("maps analysis type counts and generation state", () => {
    const type = mapInsightAnalysisType({
      key: "tiktok_viral_topic",
      name: "TikTok 爆款选题分析",
      description: "说明",
      report_count: 1,
      latest_report_at: "2026-10-31T00:00:00Z",
      generation: {
        available: false,
        reason_code: "source_not_connected",
        reason: "数据源未连接。",
      },
    });

    expect(type).toMatchObject({
      key: "tiktok_viral_topic",
      reportCount: 1,
      latestReportAt: "2026-10-31T00:00:00Z",
      generation: {
        available: false,
        reasonCode: "source_not_connected",
      },
    });
  });
});

describe("insight error descriptions", () => {
  it("keeps authentication, workspace and not-found states separate", () => {
    expect(
      describeInsightError(
        new ApiRequestError(401, "authentication_required", {
          code: "authentication_required",
        }),
        "list",
      ),
    ).toMatchObject({ kind: "auth", title: "登录已过期，请重新登录。" });

    expect(
      describeInsightError(
        new ApiRequestError(403, "workspace_not_found", {
          code: "workspace_not_found",
        }),
        "detail",
      ),
    ).toMatchObject({ kind: "workspace", title: "当前工作区不可用。" });

    expect(
      describeInsightError(
        new ApiRequestError(404, "insight_report_not_found", {
          code: "insight_report_not_found",
        }),
        "detail",
      ),
    ).toMatchObject({ kind: "not_found", title: "报告不存在或已被移除。" });
  });

  it("distinguishes content missing from integrity failure", () => {
    expect(
      describeInsightError(
        new ApiRequestError(409, "insight_report_content_missing", {
          code: "insight_report_content_missing",
        }),
        "content",
      ),
    ).toMatchObject({ kind: "content_missing" });

    expect(
      describeInsightError(
        new ApiRequestError(409, "insight_report_integrity_failed", {
          code: "insight_report_integrity_failed",
        }),
        "content",
      ),
    ).toMatchObject({ kind: "integrity_failed" });
  });

  it("does not turn a missing list endpoint into a missing report", () => {
    expect(
      describeInsightError(new ApiRequestError(404, "Not Found"), "list"),
    ).toMatchObject({
      kind: "unavailable",
      title: "无法连接服务器。",
      detail: "报告列表没有加载。",
    });
  });

  it("uses different copy for detail and content network failures", () => {
    expect(
      describeInsightError(new ApiRequestError(500, "boom"), "detail"),
    ).toMatchObject({ title: "无法加载报告。" });
    expect(
      describeInsightError(new ApiRequestError(500, "boom"), "content"),
    ).toMatchObject({ title: "无法加载报告正文。" });
  });
});

describe("insight display helpers", () => {
  it("uses the known analysis type label and falls back to the key", () => {
    expect(insightAnalysisTypeLabel("tiktok_viral_topic")).toBe(
      "TikTok 爆款选题分析",
    );
    expect(insightAnalysisTypeLabel("unknown_type")).toBe("unknown_type");
    expect(insightAnalysisTypeLabel("")).toBe("分析报告");
  });

  it("builds a stable download filename", () => {
    expect(
      insightReportDownloadFilename({
        analysisType: "tiktok_viral_topic",
        version: "2026-10-31",
        id: "report-a",
      }),
    ).toBe("tiktok-viral-topic-2026-10-31.html");
    expect(
      insightReportDownloadFilename({
        analysisType: "",
        version: "",
        id: "report-a",
      }),
    ).toBe("insight-report-report-a.html");
  });
});
