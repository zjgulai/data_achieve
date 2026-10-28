/**
 * 快速采集回执的解析。
 *
 * 后端 `QuickCollectResponse`（apps/api/src/data_intelligence_hub/services/
 * quick_collect_service.py:84）一次返回 records、output、usage、timing。
 * 这四个字段都可能为空：
 *
 * - 运行失败时没有 records；
 * - 端点不返回结构化输出时 output 是空对象；
 * - 价格簿没有该端点价格时 usage 没有金额键。
 *
 * 所以这里全部返回 null / 空数组，由调用方决定是否渲染，
 * 不用 0 冒充真实值——0 元成本和"成本未知"是两件不同的事。
 */

/** 一次回执里可展示的证据。每项独立可缺。 */
export type RunReceipt = {
  /** 耗时毫秒。取不到为 null。 */
  durationMs: number | null;
  /** 花费美元。取不到为 null；0 是合法值，表示免费端点。 */
  costUsd: number | null;
  /** 记录样本（最多 limit 条）。 */
  sample: Record<string, unknown>[];
  /** 记录总数，来自 records_count 而不是样本长度。 */
  recordsCount: number;
};

/** usage 里可能的金额键，按优先级排列。 */
const COST_KEYS = ["total_cost_usd", "cost_usd", "cost"] as const;

/** 从 usage 读金额。非有限数字一律视为缺失。 */
export function readUsageCost(usage: unknown): number | null {
  if (!usage || typeof usage !== "object") return null;
  const record = usage as Record<string, unknown>;
  for (const key of COST_KEYS) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

/** 从 timing 读耗时毫秒。 */
export function readDurationMs(timing: unknown): number | null {
  if (!timing || typeof timing !== "object") return null;
  const value = (timing as Record<string, unknown>).duration_ms;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  return null;
}

/** 把任意值压成单行短文本。对象只写类型，避免一行塞进整个 JSON。 */
export function previewValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") {
    const single = value.replace(/\s+/g, " ").trim();
    return single.length > 40 ? `${single.slice(0, 40)}…` : single;
  }
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return `[${value.length}]`;
  return "{…}";
}

/**
 * 从一条记录里挑最多 `max` 个标量字段做预览。
 *
 * 跳过对象与数组：它们是嵌套结构，压成一行没有信息量，
 * 真要看得进运行详情。
 */
export function recordPreviewEntries(
  record: Record<string, unknown>,
  max = 3,
): [string, string][] {
  const entries: [string, string][] = [];
  for (const [key, value] of Object.entries(record)) {
    if (value !== null && typeof value === "object") continue;
    entries.push([key, previewValue(value)]);
    if (entries.length >= max) break;
  }
  return entries;
}

/** 从后端响应解析出可展示的回执。任何字段缺失都不抛异常。 */
export function parseRunReceipt(
  response: {
    records?: unknown;
    usage?: unknown;
    timing?: unknown;
    output?: unknown;
    records_count?: unknown;
  },
  sampleLimit = 3,
): RunReceipt {
  const records = Array.isArray(response.records) ? response.records : [];
  const sample = records
    .filter((item): item is Record<string, unknown> =>
      item !== null && typeof item === "object" && !Array.isArray(item),
    )
    .slice(0, sampleLimit);

  const recordsCount =
    typeof response.records_count === "number" && Number.isFinite(response.records_count)
      ? response.records_count
      : records.length;

  return {
    durationMs: readDurationMs(response.timing),
    costUsd: readUsageCost(response.usage),
    sample,
    recordsCount,
  };
}
