import type { RawRecord } from "@/types/raw-record";
import type { Entity } from "@/types/entity";
import type { NotificationItem } from "@/types/notification";
import type { ProjectDomain } from "@/types/project";
import type { Signal } from "@/types/signal";
import type { CollectionTask } from "@/types/source-task";
import type { Source } from "@/types/source-task";

export const TRAINING_DATASET = "curated_training";

export function isTrainingSource(source: Source): boolean {
  return (
    getDataset(source.config) === TRAINING_DATASET ||
    getString(source.config.training_source_id).length > 0
  );
}

export function isTrainingRawRecord(record: RawRecord): boolean {
  return getDataset(record.content) === TRAINING_DATASET || getTrainingSourceId(record.content).length > 0;
}

export function getTrainingSourceId(value: unknown): string {
  const record = asRecord(value);
  const nestedContent = asRecord(record.content);
  return (
    getString(record.training_source_id) ||
    getString(record.source_id) ||
    getString(nestedContent.source_id)
  );
}

export function getTrainingCategory(value: unknown): string {
  const record = asRecord(value);
  return getString(record.category);
}

export function getTrainingRiskLevel(value: unknown): string {
  const record = asRecord(value);
  return getString(record.risk_level);
}

export function trainingCategoryLabel(value: string): string {
  const labels: Record<string, string> = {
    agent_mcp: "Agent / MCP",
    ai_extraction: "AI 抽取",
    browser_automation: "浏览器自动化",
    compliance_boundary: "合规边界",
    crawler_framework: "爬虫框架",
    official_docs: "官方文档",
    platform_method: "平台方法",
    tool_repository: "工具仓库",
  };
  return labels[value] ?? (value || "未分类");
}

export function trainingRiskLabel(value: string): string {
  const labels: Record<string, string> = {
    high: "高风险",
    low: "低风险",
    medium: "中风险",
  };
  return labels[value] ?? (value || "未标注");
}

export function isTrainingReportType(reportType: string): boolean {
  return reportType === "weekly_training";
}

export function isTrainingTask(task: CollectionTask): boolean {
  return [task.name, task.sourceName ?? ""].some((value) =>
    value.toLowerCase().includes("training"),
  );
}

export function isTrainingEntity(entity: Entity): boolean {
  return entity.externalId.startsWith("training-content:");
}

export function isTrainingProjectDomain(domain: ProjectDomain): boolean {
  return domain === "agent" || domain === "platform" || domain === "governance";
}

export function isTrainingSignal(signal: Signal): boolean {
  return getDataset(signal.metadata) === TRAINING_DATASET;
}

export function isTrainingNotification(notification: NotificationItem): boolean {
  const content = [
    notification.title,
    notification.body,
    notification.notificationType,
    notification.referenceType,
  ]
    .join(" ")
    .toLowerCase();
  return (
    content.includes("培训") ||
    content.includes("training") ||
    notification.notificationType === "alerts_ready" ||
    notification.notificationType === "evidence_ready"
  );
}

export function getTrainingSummaryLine(summary: string): string {
  return (
    summary
      .split("\n")
      .map((line) => line.trim())
      .find((line) => line.startsWith("培训讲解：")) ?? ""
  ).replace(/^培训讲解：/, "");
}

function getDataset(value: unknown): string {
  const record = asRecord(value);
  const provenance = asRecord(record.provenance);
  return getString(provenance.dataset);
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function getString(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}
