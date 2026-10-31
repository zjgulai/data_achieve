/**
 * 洞察分析报告领域类型。
 *
 * v1 只有“查看已归档报告”一种能力。类型里不出现生成进度、任务状态
 * 或 mock 报告，因为这些概念在当前版本不存在。
 */

export type InsightGenerationReasonCode =
  | "source_not_connected"
  | "mock_mode"
  | "unavailable"
  | string;

export type InsightAnalysisGeneration = {
  available: boolean;
  reasonCode: InsightGenerationReasonCode;
  reason: string;
};

export type InsightAnalysisType = {
  key: string;
  name: string;
  description: string;
  reportCount: number;
  latestReportAt: string | null;
  generation: InsightAnalysisGeneration;
};

export type InsightSourceTable = {
  schema: string;
  name: string;
  rows: number;
};

export type InsightDataScopeSource = {
  environment: string;
  database: string;
  lastWriteAt: string;
  tables: InsightSourceTable[];
};

export type InsightDataScope = {
  windowLabel: string;
  windowEnd: string;
  sampleSize: number;
  sampling: string;
  source: InsightDataScopeSource;
};

export type InsightReportStatus = "ready" | "content_missing" | string;

export type InsightSourceStatus =
  | "snapshot_only"
  | "connected"
  | "unavailable"
  | string;

export type InsightReportSummary = {
  id: string;
  analysisType: string;
  title: string;
  summary: string;
  status: InsightReportStatus;
  version: string;
  dataScope: InsightDataScope;
  sourceStatus: InsightSourceStatus;
  sourceNote: string | null;
  generatedAt: string;
  importedAt: string;
  createdBy: string | null;
  hasContent: boolean;
  contentFormat: "html" | null;
  contentBytes: number | null;
  contentSha256: string | null;
};

export type InsightReportDetail = InsightReportSummary;

export type InsightReportsQuery = {
  analysisType?: string;
  projectId?: string;
  limit?: number;
  cursor?: string;
};

export type InsightReportsPage = {
  items: InsightReportSummary[];
  nextCursor: string | null;
  /** mock 模式下为 true，页面据此显示“本地测试模式没有归档报告”。 */
  mock: boolean;
};
