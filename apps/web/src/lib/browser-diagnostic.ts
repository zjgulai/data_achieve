import type {
  BrowserDiagnosticActionPlan,
  BrowserDiagnosticActionPlanOptions,
  BrowserDiagnosticApiCandidate,
  BrowserDiagnosticBrowserAutomationDraft,
  BrowserDiagnosticCleaningRule,
  BrowserDiagnosticCounters,
  BrowserDiagnosticEvidence,
  BrowserDiagnosticFieldContractDraft,
  BrowserDiagnosticFieldContractEdit,
  BrowserDiagnosticFieldContractField,
  BrowserDiagnosticFieldStability,
  BrowserDiagnosticFit,
  BrowserDiagnosticNetworkSummary,
  BrowserDiagnosticRecommendedPath,
  BrowserDiagnosticRunPolicy,
  BrowserDiagnosticSourceDraft,
  BrowserDiagnosticStrategy,
  BrowserDiagnosticToolRecommendation,
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

export function buildBrowserDiagnosticActionPlan(
  diagnostic: BrowserStructureDiagnostic,
  options: BrowserDiagnosticActionPlanOptions = {},
): BrowserDiagnosticActionPlan {
  const fieldContract = buildFieldContractDraft(diagnostic, options);
  const blockingReasons = buildActionBlockingReasons(diagnostic);
  const primaryRecommendation = buildPrimaryToolRecommendation(diagnostic);
  const canCreateGenericWebSource =
    blockingReasons.length === 0 &&
    diagnostic.extractionStrategy.recommendedPath === "generic_web" &&
    diagnostic.extractionStrategy.fit !== "low";
  const readiness = blockingReasons.some((reason) =>
    reason.includes("生产写入标记") || reason.includes("阻断"),
  )
    ? "blocked"
    : canCreateGenericWebSource
      ? "ready"
      : "review";

  return {
    readiness,
    canCreateGenericWebSource,
    fieldContract,
    primaryRecommendation,
    secondaryRecommendations: buildSecondaryToolRecommendations(diagnostic),
    sourceDraft: canCreateGenericWebSource
      ? buildGenericWebSourceDraft(diagnostic, fieldContract)
      : null,
    browserAutomationDraft:
      diagnostic.extractionStrategy.recommendedPath === "browser_automation"
        ? buildBrowserAutomationDraft(diagnostic, fieldContract)
        : null,
    blockingReasons,
    riskControls: buildRiskControls(diagnostic),
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

function buildFieldContractDraft(
  diagnostic: BrowserStructureDiagnostic,
  options: BrowserDiagnosticActionPlanOptions,
): BrowserDiagnosticFieldContractDraft {
  const fields: BrowserDiagnosticFieldContractField[] = [
    {
      key: "page_title",
      label: "页面标题",
      valueSample: firstVisibleLine(diagnostic.visibleText.sample) || hostLabelFromUrl(diagnostic.finalUrl),
      source: "visible_text_first_line",
      required: true,
      selected: true,
      stability: diagnostic.extractionStrategy.fieldStability,
      selectorHint: "title, h1, [data-testid*=title]",
    },
    {
      key: "canonical_url",
      label: "规范 URL",
      valueSample: diagnostic.finalUrl,
      source: "browser_final_url",
      required: true,
      selected: true,
      stability: "high",
      selectorHint: "link[rel=canonical] fallback browser final_url",
    },
    {
      key: "visible_text",
      label: "正文样本",
      valueSample: diagnostic.visibleText.sample || "未提供正文样本",
      source: "browser_visible_text",
      required: true,
      selected: true,
      stability: diagnostic.extractionStrategy.fieldStability,
      selectorHint: "main, article, body visible text",
    },
  ];

  if (diagnostic.domCounters.sameOriginLinks > 0) {
    fields.push({
      key: "same_origin_links",
      label: "同源链接",
      valueSample: `${diagnostic.domCounters.sameOriginLinks} 个`,
      source: "browser_dom_links",
      required: false,
      selected: true,
      stability: "medium",
      selectorHint: "a[href^='/'], a[href^=origin]",
    });
  }

  if (diagnostic.domCounters.cards > 0) {
    fields.push({
      key: "card_count",
      label: "卡片数量",
      valueSample: `${diagnostic.domCounters.cards} 个`,
      source: "browser_dom_cards",
      required: false,
      selected: true,
      stability: diagnostic.extractionStrategy.fieldStability,
      selectorHint: "article, [class*=card], [data-testid*=card]",
    });
  }

  if (diagnostic.domCounters.forms > 0) {
    fields.push({
      key: "form_count",
      label: "表单数量",
      valueSample: `${diagnostic.domCounters.forms} 个`,
      source: "browser_dom_forms",
      required: false,
      selected: false,
      stability: "low",
      selectorHint: "form, input, button",
    });
  }

  if (diagnostic.domCounters.jsonLdBlocks > 0) {
    fields.push({
      key: "json_ld_blocks",
      label: "结构化数据块",
      valueSample: `${diagnostic.domCounters.jsonLdBlocks} 个`,
      source: "browser_json_ld",
      required: false,
      selected: true,
      stability: "high",
      selectorHint: "script[type='application/ld+json']",
    });
  }

  const firstApiCandidate = diagnostic.networkSummary.apiCandidates[0];
  if (firstApiCandidate || diagnostic.networkSummary.apiCandidateCount > 0) {
    fields.push({
      key: "api_candidate",
      label: "API 候选入口",
      valueSample: firstApiCandidate?.url ?? `${diagnostic.networkSummary.apiCandidateCount} 个候选`,
      source: "browser_network_xhr_fetch",
      required: false,
      selected: true,
      stability: diagnostic.networkSummary.xhrFetchCount > 0 ? "medium" : "low",
      selectorHint: "Network fetch/xhr candidate",
    });
  }
  const editedFields = applyFieldContractEdits(fields, options.fieldEdits ?? []);

  return {
    title: `${hostLabelFromUrl(diagnostic.finalUrl)} 字段契约草案`,
    sourceUrl: diagnostic.finalUrl,
    fields: editedFields,
    cleaningRules: buildCleaningRules(editedFields.filter((field) => field.selected)),
    evidenceSummary: [
      `浏览器证据源：${diagnostic.evidence.source}`,
      `推荐路径：${formatBrowserDiagnosticPath(diagnostic.extractionStrategy.recommendedPath)}`,
      `字段稳定性：${formatBrowserDiagnosticFieldStability(diagnostic.extractionStrategy.fieldStability)}`,
      `可见文本：${diagnostic.visibleText.length} 字符 / ${diagnostic.visibleText.lineCount} 行`,
    ],
    savedAt: options.savedAt ?? null,
  };
}

function applyFieldContractEdits(
  fields: BrowserDiagnosticFieldContractField[],
  edits: BrowserDiagnosticFieldContractEdit[],
): BrowserDiagnosticFieldContractField[] {
  if (edits.length === 0) {
    return fields;
  }
  const editsByKey = new Map(edits.map((edit) => [edit.key, edit]));
  return fields.map((field) => {
    const edit = editsByKey.get(field.key);
    if (!edit) {
      return field;
    }
    return {
      ...field,
      required: edit.required ?? field.required,
      selected: edit.selected ?? field.selected,
      selectorHint: edit.selectorHint?.trim() || field.selectorHint,
    };
  });
}

function buildCleaningRules(
  fields: BrowserDiagnosticFieldContractField[],
): BrowserDiagnosticCleaningRule[] {
  return fields.flatMap((field) => {
    if (field.key === "canonical_url" || field.key === "api_candidate") {
      return [
        {
          field: field.key,
          operation: "normalize_url",
          description: "统一 URL 结尾、协议和重定向后的最终地址。",
        },
      ];
    }
    if (field.key.endsWith("_count") || field.key === "same_origin_links" || field.key === "json_ld_blocks") {
      return [
        {
          field: field.key,
          operation: "parse_integer",
          description: "将浏览器诊断计数转换为整数，便于质量阈值判断。",
        },
      ];
    }
    return [
      {
        field: field.key,
        operation: "strip_text",
        description: "去除首尾空白并压缩连续空白字符。",
      },
    ];
  });
}

function buildActionBlockingReasons(diagnostic: BrowserStructureDiagnostic): string[] {
  const reasons: string[] = [];
  if (diagnostic.runPolicy.productionWrite) {
    reasons.push("诊断证据带有生产写入标记，必须先重新执行只读诊断。");
  }
  if (
    diagnostic.extractionStrategy.fit === "blocked" ||
    diagnostic.extractionStrategy.recommendedPath === "blocked_review"
  ) {
    reasons.push("浏览器诊断存在阻断项，不能创建采集任务。");
  }
  if (diagnostic.extractionStrategy.recommendedPath !== "generic_web") {
    reasons.push(
      `浏览器诊断推荐 ${diagnostic.extractionStrategy.recommendedPath}，不应直接创建 generic_web。`,
    );
  }
  if (diagnostic.extractionStrategy.recommendedPath === "generic_web" && diagnostic.extractionStrategy.fit === "low") {
    reasons.push("generic_web 适配度较低，需要先补充字段选择器或人工复核。");
  }
  return reasons;
}

function buildPrimaryToolRecommendation(
  diagnostic: BrowserStructureDiagnostic,
): BrowserDiagnosticToolRecommendation {
  const path = diagnostic.extractionStrategy.recommendedPath;
  const labels: Record<BrowserDiagnosticRecommendedPath, string> = {
    blocked_review: "授权和边界复核",
    browser_automation: "browser-harness + Playwright/Crawlee",
    generic_web: "generic_web 公开页面采集",
    manual_review: "人工复核与样本标注",
    official_api_or_file: "官方 API / 文件导入",
  };
  const collectorTypes: Record<BrowserDiagnosticRecommendedPath, string> = {
    blocked_review: "manual_review",
    browser_automation: "external_browser_automation",
    generic_web: "generic_web",
    manual_review: "manual_json",
    official_api_or_file: "manual_json",
  };
  return {
    toolFamily: path,
    toolLabel: labels[path],
    collectorType: collectorTypes[path],
    fit: diagnostic.extractionStrategy.fit,
    riskLevel: riskLevelForDiagnostic(diagnostic),
    reason: primaryRecommendationReason(diagnostic),
    nextActions: diagnostic.extractionStrategy.nextSteps.length > 0
      ? diagnostic.extractionStrategy.nextSteps
      : ["复核字段契约、保存只读证据，再创建采集任务。"],
  };
}

function buildSecondaryToolRecommendations(
  diagnostic: BrowserStructureDiagnostic,
): BrowserDiagnosticToolRecommendation[] {
  const recommendations: BrowserDiagnosticToolRecommendation[] = [];
  if (
    diagnostic.networkSummary.apiCandidateCount > 0 &&
    diagnostic.extractionStrategy.recommendedPath !== "official_api_or_file"
  ) {
    recommendations.push({
      toolFamily: "official_api_or_file",
      toolLabel: "API 候选复核",
      collectorType: "manual_json",
      fit: "medium",
      riskLevel: "medium",
      reason: "浏览器网络记录发现 fetch/xhr 候选，可能存在更稳定的数据接口。",
      nextActions: ["确认接口授权、参数和分页方式。", "不要在未授权接口上执行批量请求。"],
    });
  }
  if (
    diagnostic.domCounters.forms > 0 &&
    diagnostic.extractionStrategy.recommendedPath !== "manual_review"
  ) {
    recommendations.push({
      toolFamily: "manual_review",
      toolLabel: "表单/登录边界复核",
      collectorType: "manual_json",
      fit: "medium",
      riskLevel: "high",
      reason: "页面存在表单元素，采集前需要确认是否涉及登录、提交或个人数据。",
      nextActions: ["确认只读路径。", "禁止自动提交表单或改写远端状态。"],
    });
  }
  return recommendations;
}

function buildGenericWebSourceDraft(
  diagnostic: BrowserStructureDiagnostic,
  fieldContract: BrowserDiagnosticFieldContractDraft,
): BrowserDiagnosticSourceDraft {
  const selectedFields = fieldContract.fields.filter((field) => field.selected);
  return {
    type: "generic_web",
    suggestedName: `Browser Diagnostic: ${hostLabelFromUrl(diagnostic.finalUrl)}`,
    url: diagnostic.finalUrl,
    config: {
      url: diagnostic.finalUrl,
      extract_mode: "main_content",
      fields: selectedFields.map((field) => field.key),
      browser_diagnostic: {
        schema_version: diagnostic.schemaVersion,
        final_url: diagnostic.finalUrl,
        recommended_path: diagnostic.extractionStrategy.recommendedPath,
        confidence: diagnostic.extractionStrategy.confidence,
        field_stability: diagnostic.extractionStrategy.fieldStability,
        evidence_source: diagnostic.evidence.source,
        screenshot_path: diagnostic.evidence.screenshotPath,
      },
      field_contract: {
        fields: selectedFields.map((field) => ({
          key: field.key,
          label: field.label,
          source: field.source,
          required: field.required,
          selected: field.selected,
          selector_hint: field.selectorHint,
        })),
        cleaning_rules: fieldContract.cleaningRules,
      },
    },
  };
}

function buildBrowserAutomationDraft(
  diagnostic: BrowserStructureDiagnostic,
  fieldContract: BrowserDiagnosticFieldContractDraft,
): BrowserDiagnosticBrowserAutomationDraft {
  const selectedFields = fieldContract.fields.filter((field) => field.selected);
  return {
    type: "browser_automation",
    runner: "browser_harness",
    suggestedName: `Browser Automation: ${hostLabelFromUrl(diagnostic.finalUrl)}`,
    config: {
      start_url: diagnostic.finalUrl,
      execution_mode: "read_only_browser_harness",
      recommended_tools: ["browser-harness", "Playwright", "Crawlee"],
      api_candidates: diagnostic.networkSummary.apiCandidates.map((candidate) => candidate.url),
      field_contract: {
        fields: selectedFields.map((field) => ({
          key: field.key,
          label: field.label,
          source: field.source,
          required: field.required,
          selected: field.selected,
          selector_hint: field.selectorHint,
        })),
        cleaning_rules: fieldContract.cleaningRules,
      },
    },
    guardrails: [
      "只读执行，不提交表单、不点击购买或发布类按钮。",
      "必须保留诊断 JSON、截图路径和最终 URL 作为审计证据。",
      "先小批量验证字段稳定性，再进入任务调度。",
    ],
  };
}

function buildRiskControls(diagnostic: BrowserStructureDiagnostic): string[] {
  const controls = [
    diagnostic.runPolicy.authorizationConfirmed
      ? "授权已确认，但创建任务前仍需保留证据。"
      : "授权未确认，不能进入真实采集。",
    diagnostic.runPolicy.productionWrite
      ? "当前诊断存在写入标记，必须重跑只读诊断。"
      : "当前诊断标记为只读证据。",
    "字段契约进入任务配置前，需要保留 screenshot 或诊断 JSON 作为审计证据。",
  ];
  if (diagnostic.riskFlags.length > 0) {
    controls.push(`风险标记：${diagnostic.riskFlags.join(" / ")}`);
  }
  return controls;
}

function primaryRecommendationReason(diagnostic: BrowserStructureDiagnostic): string {
  const strategy = diagnostic.extractionStrategy;
  if (strategy.reasons.length > 0) {
    return strategy.reasons[0];
  }
  if (strategy.recommendedPath === "generic_web") {
    return "页面渲染后可见文本和链接可直接读取，优先从公开页面主内容采集。";
  }
  if (strategy.recommendedPath === "browser_automation") {
    return "页面结构依赖浏览器渲染或交互，需要真实浏览器证据驱动的自动化方案。";
  }
  if (strategy.recommendedPath === "official_api_or_file") {
    return "浏览器诊断显示更适合使用授权 API 或文件数据源。";
  }
  return "浏览器诊断需要人工复核后才能进入任务创建。";
}

function riskLevelForDiagnostic(
  diagnostic: BrowserStructureDiagnostic,
): BrowserDiagnosticToolRecommendation["riskLevel"] {
  if (
    diagnostic.runPolicy.productionWrite ||
    diagnostic.extractionStrategy.fit === "blocked" ||
    diagnostic.extractionStrategy.recommendedPath === "blocked_review"
  ) {
    return "high";
  }
  if (
    diagnostic.riskFlags.length > 0 ||
    diagnostic.domCounters.forms > 0 ||
    diagnostic.extractionStrategy.recommendedPath !== "generic_web"
  ) {
    return "medium";
  }
  return "low";
}

function firstVisibleLine(sample: string): string {
  return sample
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean) ?? "";
}

function hostLabelFromUrl(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
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
