export type AuditFact = {
  label: string;
  value: string;
};

const internalKeys = new Set([
  "contenthash",
  "contentpath",
  "createdat",
  "current",
  "currentsnapshotid",
  "detectedat",
  "errortraceback",
  "finishedat",
  "jsonpaths",
  "previous",
  "previoussnapshotid",
  "projectid",
  "rawrecordid",
  "screenshoturl",
  "seedversion",
  "snapshotid",
  "snapshotids",
  "snapshotstrategy",
  "sourceid",
  "sourcelayer",
  "startedat",
  "taskid",
  "taskrunid",
  "updatedat",
  "workspaceid",
]);

const labelMap: Record<string, string> = {
  change_ratio: "变化比例",
  claim_type: "证据类型",
  collection_method: "采集方式",
  collection_methods: "采集方法",
  confidence: "置信度",
  currency: "币种",
  delta_ratio: "变化幅度",
  engagement_rate: "互动率",
  excerpt: "证据摘录",
  forks: "Forks",
  full_name: "仓库",
  html_length: "HTML 长度",
  method_quality: "方法质量",
  metric: "指标",
  mentions_24h: "24h 提及量",
  name: "名称",
  open_issues: "Open Issues",
  price: "价格",
  quote: "命中文本",
  rank: "排名",
  review_count: "评论数",
  stars: "Stars",
  text_length: "文本长度",
  threshold: "阈值",
  title: "标题",
  url: "来源 URL",
  window: "时间窗口",
};

export function buildAuditFacts(value: unknown, maxItems = 10): AuditFact[] {
  const facts: AuditFact[] = [];
  collectFacts(value, "", facts, maxItems);
  return facts.slice(0, maxItems);
}

export function getAuditFactCount(value: unknown): number {
  return buildAuditFacts(value, 100).length;
}

function collectFacts(value: unknown, key: string, facts: AuditFact[], maxItems: number) {
  if (facts.length >= maxItems || isEmptyValue(value)) {
    return;
  }

  if (Array.isArray(value)) {
    const primitiveItems = value.filter((item) => isPrimitive(item));
    if (primitiveItems.length > 0 && key && !isInternalKey(key)) {
      facts.push({
        label: formatAuditLabel(key),
        value: primitiveItems.map(formatAuditValue).join(" / "),
      });
    }
    return;
  }

  if (isPrimitive(value)) {
    if (key && !isInternalKey(key) && !isTechnicalValue(value)) {
      facts.push({ label: formatAuditLabel(key), value: formatAuditValue(value) });
    }
    return;
  }

  if (!isPlainRecord(value)) {
    return;
  }

  const payload = value.payload;
  if (isPlainRecord(payload) || Array.isArray(payload)) {
    collectFacts(payload, key, facts, maxItems);
  }

  for (const [entryKey, entryValue] of Object.entries(value)) {
    if (facts.length >= maxItems || entryKey === "payload" || isInternalKey(entryKey)) {
      continue;
    }
    collectFacts(entryValue, entryKey, facts, maxItems);
  }
}

function isInternalKey(key: string): boolean {
  const normalized = key.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
  return normalized === "provenance" || internalKeys.has(normalized);
}

function isTechnicalValue(value: string | number | boolean): boolean {
  if (typeof value !== "string") {
    return false;
  }
  return (
    /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(value) ||
    /^[0-9a-f]{24,}$/i.test(value) ||
    value.includes("$.") ||
    value.includes("data_intelligence_hub.") ||
    value === "demo_seed"
  );
}

function formatAuditLabel(key: string): string {
  return (
    labelMap[key] ??
    labelMap[key.replace(/[A-Z]/g, (match) => `_${match.toLowerCase()}`)] ??
    key
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase())
  );
}

function formatAuditValue(value: string | number | boolean): string {
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }
  return value;
}

function isPrimitive(value: unknown): value is string | number | boolean {
  return ["string", "number", "boolean"].includes(typeof value);
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isEmptyValue(value: unknown): boolean {
  return value === null || value === undefined || value === "";
}
