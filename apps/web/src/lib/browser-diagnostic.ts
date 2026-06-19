import type {
  BrowserDiagnosticApiCandidate,
  BrowserDiagnosticCounters,
  BrowserDiagnosticEvidence,
  BrowserDiagnosticFieldStability,
  BrowserDiagnosticFit,
  BrowserDiagnosticNetworkSummary,
  BrowserDiagnosticRecommendedPath,
  BrowserDiagnosticRunPolicy,
  BrowserDiagnosticStrategy,
  BrowserDiagnosticVisibleText,
  BrowserStructureDiagnostic,
} from "@/types/browser-diagnostic";
import type { ToolkitPreflightReport } from "@/types/toolkit";

const browserDiagnosticSchemaVersion = "browser_structure_diagnostic.v1";
const recommendedPaths: BrowserDiagnosticRecommendedPath[] = [
  "generic_web",
  "browser_automation",
  "official_api_or_file",
  "manual_review",
  "blocked_review",
];
const strategyFits: BrowserDiagnosticFit[] = ["high", "medium", "low", "blocked"];
const fieldStabilities: BrowserDiagnosticFieldStability[] = ["high", "medium", "low"];

export type BrowserDiagnosticParseResult =
  | { ok: true; diagnostic: BrowserStructureDiagnostic }
  | { ok: false; error: string };

export type BrowserDiagnosticComparison = {
  staticPath: BrowserDiagnosticRecommendedPath | null;
  browserPath: BrowserDiagnosticRecommendedPath;
  pathAgreement: boolean | null;
  message: string;
  severity: "aligned" | "review" | "blocked";
};

export function parseBrowserStructureDiagnosticJson(
  rawJson: string,
): BrowserDiagnosticParseResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawJson);
  } catch {
    return { ok: false, error: "JSON 无法解析，请检查格式。" };
  }
  if (!isRecord(parsed)) {
    return { ok: false, error: "诊断内容必须是 JSON 对象。" };
  }
  if (readString(parsed, "schema_version") !== browserDiagnosticSchemaVersion) {
    return { ok: false, error: "仅支持 browser_structure_diagnostic.v1。" };
  }

  const extractionStrategy = mapStrategy(parsed.extraction_strategy);
  if (extractionStrategy === null) {
    return { ok: false, error: "缺少有效的 extraction_strategy。" };
  }
  const finalUrl = readString(parsed, "final_url");
  if (!finalUrl) {
    return { ok: false, error: "缺少 final_url。" };
  }

  return {
    ok: true,
    diagnostic: {
      schemaVersion: browserDiagnosticSchemaVersion,
      generatedAt: readString(parsed, "generated_at"),
      requestedUrl: readString(parsed, "requested_url"),
      finalUrl,
      runPolicy: mapRunPolicy(parsed.run_policy),
      visibleText: mapVisibleText(parsed.visible_text),
      domCounters: mapCounters(parsed.dom_counters),
      riskFlags: readStringArray(parsed, "risk_flags"),
      extractionStrategy,
      networkSummary: mapNetworkSummary(parsed.network_summary),
      evidence: mapEvidence(parsed.evidence),
    },
  };
}

export function comparePreflightWithBrowserDiagnostic(
  preflightReport: ToolkitPreflightReport | null | undefined,
  diagnostic: BrowserStructureDiagnostic,
): BrowserDiagnosticComparison {
  const staticPath = preflightReport?.collectionStrategy.recommendedPath ?? null;
  const browserPath = diagnostic.extractionStrategy.recommendedPath;
  if (diagnostic.extractionStrategy.fit === "blocked") {
    return {
      staticPath,
      browserPath,
      pathAgreement: staticPath === null ? null : staticPath === browserPath,
      message: "浏览器诊断存在阻断项，先复核授权和页面边界。",
      severity: "blocked",
    };
  }
  if (staticPath === null) {
    return {
      staticPath,
      browserPath,
      pathAgreement: null,
      message: "已导入浏览器诊断，可作为后续字段契约和采集方式判断依据。",
      severity: "review",
    };
  }
  if (staticPath === browserPath) {
    return {
      staticPath,
      browserPath,
      pathAgreement: true,
      message: "静态预检与真实浏览器诊断路径一致，可继续按当前路径设计采集方案。",
      severity: "aligned",
    };
  }
  return {
    staticPath,
    browserPath,
    pathAgreement: false,
    message: "真实浏览器诊断与静态预检不同，优先复核浏览器证据后再建采集任务。",
    severity: "review",
  };
}

export function formatBrowserDiagnosticPath(value: BrowserDiagnosticRecommendedPath): string {
  const labels: Record<BrowserDiagnosticRecommendedPath, string> = {
    blocked_review: "阻断复核",
    browser_automation: "浏览器自动化",
    generic_web: "静态页面采集",
    manual_review: "人工复核",
    official_api_or_file: "API/文件导入",
  };
  return labels[value];
}

export function formatBrowserDiagnosticFit(value: BrowserDiagnosticFit): string {
  const labels: Record<BrowserDiagnosticFit, string> = {
    blocked: "阻断",
    high: "高适配",
    low: "低适配",
    medium: "中适配",
  };
  return labels[value];
}

export function formatBrowserDiagnosticFieldStability(
  value: BrowserDiagnosticFieldStability,
): string {
  const labels: Record<BrowserDiagnosticFieldStability, string> = {
    high: "高",
    low: "低",
    medium: "中",
  };
  return labels[value];
}

function mapStrategy(value: unknown): BrowserDiagnosticStrategy | null {
  if (!isRecord(value)) {
    return null;
  }
  const recommendedPath = readEnum(value, "recommended_path", recommendedPaths);
  const fit = readEnum(value, "fit", strategyFits);
  const fieldStability = readEnum(value, "field_stability", fieldStabilities);
  if (!recommendedPath || !fit || !fieldStability) {
    return null;
  }
  return {
    recommendedPath,
    fit,
    confidence: clampNumber(readNumber(value, "confidence"), 0, 100),
    fieldStability,
    reasons: readStringArray(value, "reasons"),
    nextSteps: readStringArray(value, "next_steps"),
    cleaningNotes: readStringArray(value, "cleaning_notes"),
  };
}

function mapRunPolicy(value: unknown): BrowserDiagnosticRunPolicy {
  const record = isRecord(value) ? value : {};
  return {
    authorizationConfirmed: readBoolean(record, "authorization_confirmed"),
    executionMode: readString(record, "execution_mode"),
    productionWrite: readBoolean(record, "production_write"),
    loginOrPrivatePageAllowed: readBoolean(record, "login_or_private_page_allowed"),
    cookiesExported: readBoolean(record, "cookies_exported"),
    note: readString(record, "note") || null,
  };
}

function mapVisibleText(value: unknown): BrowserDiagnosticVisibleText {
  const record = isRecord(value) ? value : {};
  return {
    length: readNumber(record, "length"),
    lineCount: readNumber(record, "line_count"),
    sample: readString(record, "sample"),
  };
}

function mapCounters(value: unknown): BrowserDiagnosticCounters {
  const record = isRecord(value) ? value : {};
  return {
    links: readNumber(record, "links"),
    sameOriginLinks: readNumber(record, "same_origin_links"),
    externalLinks: readNumber(record, "external_links"),
    forms: readNumber(record, "forms"),
    inputs: readNumber(record, "inputs"),
    buttons: readNumber(record, "buttons"),
    tables: readNumber(record, "tables"),
    lists: readNumber(record, "lists"),
    articles: readNumber(record, "articles"),
    cards: readNumber(record, "cards"),
    images: readNumber(record, "images"),
    scripts: readNumber(record, "scripts"),
    stylesheets: readNumber(record, "stylesheets"),
    jsonLdBlocks: readNumber(record, "json_ld_blocks"),
  };
}

function mapNetworkSummary(value: unknown): BrowserDiagnosticNetworkSummary {
  const record = isRecord(value) ? value : {};
  return {
    resourceCount: readNumber(record, "resource_count"),
    sameOriginResources: readNumber(record, "same_origin_resources"),
    crossOriginResources: readNumber(record, "cross_origin_resources"),
    xhrFetchCount: readNumber(record, "xhr_fetch_count"),
    scriptCount: readNumber(record, "script_count"),
    imageCount: readNumber(record, "image_count"),
    apiCandidateCount: readNumber(record, "api_candidate_count"),
    apiCandidates: readApiCandidates(record.api_candidates),
    initiatorTypeCounts: readNumberRecord(record.initiator_type_counts),
  };
}

function mapEvidence(value: unknown): BrowserDiagnosticEvidence {
  const record = isRecord(value) ? value : {};
  return {
    screenshotPath: readString(record, "screenshot_path") || null,
    source: readString(record, "source") || "browser-harness",
    errors: readStringArray(record, "errors"),
  };
}

function readApiCandidates(value: unknown): BrowserDiagnosticApiCandidate[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isRecord).map((item) => ({
    url: readString(item, "url"),
    initiatorType: readString(item, "initiator_type"),
    sameOrigin: readBoolean(item, "same_origin"),
    durationMs: readNumber(item, "duration_ms"),
    transferSize: readNumber(item, "transfer_size"),
  }));
}

function readNumberRecord(value: unknown): Record<string, number> {
  if (!isRecord(value)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [key, toNumber(item)]),
  );
}

function readString(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === "string" ? value.trim() : "";
}

function readNumber(record: Record<string, unknown>, key: string): number {
  return toNumber(record[key]);
}

function readBoolean(record: Record<string, unknown>, key: string): boolean {
  return record[key] === true;
}

function readStringArray(record: Record<string, unknown>, key: string): string[] {
  const value = record[key];
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
}

function readEnum<T extends string>(
  record: Record<string, unknown>,
  key: string,
  allowed: readonly T[],
): T | null {
  const value = record[key];
  return typeof value === "string" && allowed.includes(value as T) ? (value as T) : null;
}

function toNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function clampNumber(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
