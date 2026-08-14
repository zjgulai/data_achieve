import { ApiRequestError } from "@/lib/api/client";
import { mapPlannerValidationIssues } from "@/lib/api/workflow-plans";
import type { CapabilityPlatform } from "@/types/capability";
import type {
  BudgetCeiling,
  DeliveryIntent,
  MonitoringScopeDraft,
  MonitoringScopeType,
  PlanningInput,
  RateLimitIntent,
  RetentionIntent,
  ScheduleIntent,
  WorkflowPlanPreview,
  WorkflowPlannerMode,
  WorkflowPlannerPurpose,
} from "@/types/workflow-planner";

export type PlannerStep = "mode" | "scopes" | "constraints" | "preview";

export type PlannerFieldIssue = {
  fieldId: string;
  message: string;
};

export type PlannerFieldErrors = Record<string, string>;

export type MonitoringScopeFormDraft = MonitoringScopeDraft;

export type WorkflowPlannerDraft = {
  mode: WorkflowPlannerMode;
  purpose: WorkflowPlannerPurpose;
  scopes: MonitoringScopeFormDraft[];
  defaultLanguages: string[];
  defaultRegions: string[];
  defaultPlatforms: CapabilityPlatform[];
  scheduleIntent: ScheduleIntent | null;
  deliveryIntent: DeliveryIntent | null;
  requiredFields: string[];
  optionalFields: string[];
  budgetCeiling: BudgetCeiling | null;
  rateLimitIntent: RateLimitIntent | null;
  retentionIntent: RetentionIntent | null;
  allowPartialDegradation: boolean;
  revision: number;
  nextScopeSequence: number;
};

export type PreviewSemanticContext = {
  projectId: string | null;
  mode: WorkflowPlannerMode;
  formRevision: number;
};

export type PreviewSnapshot = {
  projectId: string;
  mode: WorkflowPlannerMode;
  formRevision: number;
  previewInput: PlanningInput;
  preview: WorkflowPlanPreview;
};

export type PreviewRequestState =
  | { status: "idle" }
  | { status: "loading"; sequence: number; previous?: PreviewSnapshot }
  | { status: "success"; snapshot: PreviewSnapshot; stale: boolean }
  | {
      status: "error";
      message: string;
      requestId: string | null;
      httpStatus: number | null;
      retryable: boolean;
      fieldErrors: PlannerFieldErrors;
    };

export type PreviewErrorState = Extract<
  PreviewRequestState,
  { status: "error" }
>;

export function isPreviewSnapshotCurrent(
  snapshot: PreviewSnapshot,
  context: PreviewSemanticContext,
): boolean {
  return (
    snapshot.projectId === context.projectId &&
    snapshot.mode === context.mode &&
    snapshot.formRevision === context.formRevision
  );
}

export function shouldAcceptPreviewResponse(input: {
  responseSequence: number;
  currentSequence: number;
  responseContext: PreviewSemanticContext;
  currentContext: PreviewSemanticContext;
}): boolean {
  return (
    input.responseSequence === input.currentSequence &&
    input.responseContext.projectId === input.currentContext.projectId &&
    input.responseContext.mode === input.currentContext.mode &&
    input.responseContext.formRevision === input.currentContext.formRevision
  );
}

export function invalidatePreviewRequest(
  state: PreviewRequestState,
): PreviewRequestState {
  if (state.status === "success") {
    return { ...state, stale: true };
  }
  if (state.status === "loading" && state.previous) {
    return { status: "success", snapshot: state.previous, stale: true };
  }
  return { status: "idle" };
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}

export function createPreviewErrorState(
  error: unknown,
): PreviewErrorState | null {
  if (isAbortError(error)) {
    return null;
  }
  if (error instanceof ApiRequestError) {
    return {
      status: "error",
      message: error.message,
      requestId: error.requestId,
      httpStatus: error.status,
      retryable: error.status >= 500,
      fieldErrors:
        error.status === 422
          ? mapPlannerValidationIssues(error.validationIssues)
          : {},
    };
  }
  return {
    status: "error",
    message: error instanceof Error ? error.message : "Preview 请求失败",
    requestId: null,
    httpStatus: null,
    retryable: true,
    fieldErrors: {},
  };
}

const canonicalRequiredTypes = new Set<MonitoringScopeType>([
  "brand",
  "category",
  "competitor",
]);
const seedCapableTypes = new Set<MonitoringScopeType>(["topic", "campaign"]);

function normalizedText(value: string): string {
  return value.normalize("NFKC").trim();
}

function comparisonKey(value: string): string {
  return normalizedText(value).toLowerCase();
}

export function normalizePlannerList(values: readonly string[]): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const value of values) {
    const displayValue = normalizedText(value);
    const key = comparisonKey(displayValue);
    if (!displayValue || seen.has(key)) {
      continue;
    }
    seen.add(key);
    normalized.push(displayValue);
  }
  return normalized;
}

function uniqueValues<T extends string>(values: readonly T[]): T[] {
  return [...new Set(values)];
}

function hasScopeQueryInput(scope: MonitoringScopeFormDraft): boolean {
  return Boolean(
    normalizedText(scope.canonicalTerm ?? "") ||
    normalizePlannerList(scope.aliases).length ||
    normalizePlannerList(scope.includeTerms).length ||
    normalizePlannerList(scope.officialAccounts).length,
  );
}

function hasAnyScopeInput(scope: MonitoringScopeFormDraft): boolean {
  return (
    hasScopeQueryInput(scope) || normalizePlannerList(scope.seedUrls).length > 0
  );
}

function isValidSeedUrl(value: string): boolean {
  const candidate = normalizedText(value);
  if (!candidate) {
    return true;
  }
  try {
    const parsed = new URL(candidate);
    return (
      (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      Boolean(parsed.hostname)
    );
  } catch {
    return false;
  }
}

function issue(fieldId: string, message: string): PlannerFieldIssue {
  return { fieldId, message };
}

export function parseWorkflowPlannerMode(
  value: string | string[] | null | undefined,
): WorkflowPlannerMode {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate === "batch_research" || candidate === "periodic_monitoring"
    ? candidate
    : "periodic_monitoring";
}

export type WorkflowPlannerRouteContext = {
  mode: WorkflowPlannerMode;
  projectId: string | null;
  planId: string | null;
  sourceVersionId: string | null;
  error: string | null;
};

function firstQueryValue(
  value: string | string[] | null | undefined,
): string | null {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (typeof candidate !== "string") {
    return null;
  }
  return normalizedText(candidate) || null;
}

export function parseWorkflowPlannerRouteQuery(
  query: Record<string, string | string[] | null | undefined>,
): WorkflowPlannerRouteContext {
  const mode = parseWorkflowPlannerMode(query.mode);
  const projectId = firstQueryValue(query.project_id);
  const planId = firstQueryValue(query.plan_id);
  const sourceVersionId = firstQueryValue(query.source_version_id);
  let error: string | null = null;
  if (sourceVersionId && (!planId || !projectId)) {
    error = "source_version_id requires plan_id and project_id";
  } else if (planId && !projectId) {
    error = "plan_id requires project_id";
  }
  return { mode, projectId, planId, sourceVersionId, error };
}

export function createScopeDraft(
  sequence: number,
  scopeType: MonitoringScopeType = "brand",
): MonitoringScopeFormDraft {
  if (!Number.isSafeInteger(sequence) || sequence < 1) {
    throw new RangeError("Scope sequence must be a positive safe integer");
  }
  return {
    scopeRef: `scope-${sequence}`,
    scopeType,
    canonicalTerm: null,
    aliases: [],
    includeTerms: [],
    excludeTerms: [],
    officialAccounts: [],
    seedUrls: [],
    languages: [],
    regions: [],
    platforms: [],
    matchMode: null,
  };
}

export function createWorkflowPlannerDraft(
  mode: WorkflowPlannerMode,
): WorkflowPlannerDraft {
  return {
    mode,
    purpose:
      mode === "periodic_monitoring" ? "brand_monitoring" : "market_research",
    scopes: [createScopeDraft(1)],
    defaultLanguages: [],
    defaultRegions: [],
    defaultPlatforms: [],
    scheduleIntent: null,
    deliveryIntent: null,
    requiredFields: [],
    optionalFields: [],
    budgetCeiling: null,
    rateLimitIntent: null,
    retentionIntent: null,
    allowPartialDegradation: false,
    revision: 0,
    nextScopeSequence: 2,
  };
}

export function clonePlanningInput(input: PlanningInput): PlanningInput {
  const base = {
    scopes: input.scopes.map((scope) => ({
      ...scope,
      aliases: [...scope.aliases],
      includeTerms: [...scope.includeTerms],
      excludeTerms: [...scope.excludeTerms],
      officialAccounts: [...scope.officialAccounts],
      seedUrls: [...scope.seedUrls],
      languages: [...scope.languages],
      regions: [...scope.regions],
      platforms: [...scope.platforms],
    })),
    defaultLanguages: [...input.defaultLanguages],
    defaultRegions: [...input.defaultRegions],
    defaultPlatforms: [...input.defaultPlatforms],
    deliveryIntent: input.deliveryIntent
      ? { outputs: [...input.deliveryIntent.outputs] }
      : null,
    policyProfile: input.policyProfile,
    purpose: input.purpose,
    requiredFields: [...input.requiredFields],
    optionalFields: [...input.optionalFields],
    budgetCeiling: input.budgetCeiling ? { ...input.budgetCeiling } : null,
    rateLimitIntent: input.rateLimitIntent
      ? { ...input.rateLimitIntent }
      : null,
    retentionIntent: input.retentionIntent
      ? { ...input.retentionIntent }
      : null,
    allowPartialDegradation: input.allowPartialDegradation,
  };
  if (input.flowMode === "periodic_monitoring") {
    return {
      ...base,
      flowMode: input.flowMode,
      scheduleIntent: { ...input.scheduleIntent },
    };
  }
  return { ...base, flowMode: input.flowMode };
}

function nextScopeSequence(
  scopes: readonly MonitoringScopeFormDraft[],
): number {
  let maximum = 0;
  for (const scope of scopes) {
    const match = /^scope-(\d+)$/.exec(scope.scopeRef);
    if (match) {
      maximum = Math.max(maximum, Number(match[1]));
    }
  }
  return Math.max(maximum + 1, scopes.length + 1, 1);
}

export function workflowPlannerDraftFromEditableInput(
  editableInput: PlanningInput,
): WorkflowPlannerDraft {
  const input = clonePlanningInput(editableInput);
  return {
    mode: input.flowMode,
    purpose: input.purpose,
    scopes: input.scopes,
    defaultLanguages: input.defaultLanguages,
    defaultRegions: input.defaultRegions,
    defaultPlatforms: input.defaultPlatforms,
    scheduleIntent:
      input.flowMode === "periodic_monitoring" ? input.scheduleIntent : null,
    deliveryIntent: input.deliveryIntent,
    requiredFields: input.requiredFields,
    optionalFields: input.optionalFields,
    budgetCeiling: input.budgetCeiling,
    rateLimitIntent: input.rateLimitIntent,
    retentionIntent: input.retentionIntent,
    allowPartialDegradation: input.allowPartialDegradation,
    revision: 0,
    nextScopeSequence: nextScopeSequence(input.scopes),
  };
}

export function workflowPlannerDraftSemanticKey(
  draft: WorkflowPlannerDraft,
): string {
  return JSON.stringify({
    mode: draft.mode,
    purpose: draft.purpose,
    scopes: draft.scopes,
    defaultLanguages: draft.defaultLanguages,
    defaultRegions: draft.defaultRegions,
    defaultPlatforms: draft.defaultPlatforms,
    scheduleIntent: draft.scheduleIntent,
    deliveryIntent: draft.deliveryIntent,
    requiredFields: draft.requiredFields,
    optionalFields: draft.optionalFields,
    budgetCeiling: draft.budgetCeiling,
    rateLimitIntent: draft.rateLimitIntent,
    retentionIntent: draft.retentionIntent,
    allowPartialDegradation: draft.allowPartialDegradation,
  });
}

export function addScopeDraft(
  draft: WorkflowPlannerDraft,
  scopeType: MonitoringScopeType = "brand",
): WorkflowPlannerDraft {
  if (draft.scopes.length >= 20) {
    throw new RangeError("A Preview accepts at most 20 Scopes");
  }
  return {
    ...draft,
    scopes: [
      ...draft.scopes,
      createScopeDraft(draft.nextScopeSequence, scopeType),
    ],
    nextScopeSequence: draft.nextScopeSequence + 1,
    revision: draft.revision + 1,
  };
}

export function removeScopeDraft(
  draft: WorkflowPlannerDraft,
  scopeRef: string,
): WorkflowPlannerDraft {
  if (draft.scopes.length === 1 && draft.scopes[0]?.scopeRef === scopeRef) {
    throw new RangeError("A Planner draft must keep at least one Scope");
  }
  const scopes = draft.scopes.filter((scope) => scope.scopeRef !== scopeRef);
  if (scopes.length === draft.scopes.length) {
    return draft;
  }
  return { ...draft, scopes, revision: draft.revision + 1 };
}

function validateModeStep(draft: WorkflowPlannerDraft): PlannerFieldIssue[] {
  const issues: PlannerFieldIssue[] = [];
  if (draft.mode !== "periodic_monitoring" && draft.mode !== "batch_research") {
    issues.push(issue("planner-mode", "请选择规划模式"));
  }
  if (
    draft.purpose !== "brand_monitoring" &&
    draft.purpose !== "market_research" &&
    draft.purpose !== "competitive_research"
  ) {
    issues.push(issue("planner-purpose", "请选择业务目标"));
  }
  return issues;
}

function validateScopeStep(draft: WorkflowPlannerDraft): PlannerFieldIssue[] {
  const issues: PlannerFieldIssue[] = [];
  if (draft.scopes.length === 0) {
    return [issue("planner-scopes", "至少需要一个 Scope")];
  }
  if (draft.scopes.length > 20) {
    issues.push(issue("planner-scopes", "单次 Preview 最多 20 个 Scope"));
  }

  const seenRefs = new Set<string>();
  let totalSeedUrls = 0;
  draft.scopes.forEach((scope, index) => {
    const canonicalTerm = normalizedText(scope.canonicalTerm ?? "");
    if (seenRefs.has(scope.scopeRef)) {
      issues.push(
        issue(`planner-scope-${index}-type`, "Scope 引用必须保持唯一"),
      );
    }
    seenRefs.add(scope.scopeRef);

    if (canonicalRequiredTypes.has(scope.scopeType) && !canonicalTerm) {
      issues.push(
        issue(
          `planner-scope-${index}-canonical-term`,
          "品牌、品类和竞品 Scope 需要核心词",
        ),
      );
    }
    if (seedCapableTypes.has(scope.scopeType) && !hasAnyScopeInput(scope)) {
      issues.push(
        issue(
          `planner-scope-${index}-canonical-term`,
          "请填写核心词、别名、包含词、账号或 Seed URL",
        ),
      );
    }

    const limitedLists: Array<[readonly string[], string]> = [
      [scope.aliases, "aliases"],
      [scope.includeTerms, "include-terms"],
      [scope.excludeTerms, "exclude-terms"],
      [scope.officialAccounts, "official-accounts"],
    ];
    for (const [values, suffix] of limitedLists) {
      if (values.length > 50) {
        issues.push(
          issue(`planner-scope-${index}-${suffix}`, "每个词项列表最多 50 项"),
        );
      }
    }
    if (scope.seedUrls.length > 100) {
      issues.push(
        issue(
          `planner-scope-${index}-seed-urls`,
          "每个 Scope 最多接受 100 个 Seed URL",
        ),
      );
    }
    scope.seedUrls.forEach((seedUrl, urlIndex) => {
      if (!isValidSeedUrl(seedUrl)) {
        issues.push(
          issue(
            `planner-scope-${index}-seed-url-${urlIndex}`,
            "Seed URL 必须是包含 hostname 的 HTTP(S) URL",
          ),
        );
      }
    });
    totalSeedUrls += scope.seedUrls.length;
  });
  if (totalSeedUrls > 100) {
    issues.push(
      issue("planner-scopes", "单次 Preview 最多接受 100 个 Seed URL"),
    );
  }
  return issues;
}

function validateConstraintStep(
  draft: WorkflowPlannerDraft,
): PlannerFieldIssue[] {
  const issues: PlannerFieldIssue[] = [];
  const defaultsHavePlatform = uniqueValues(draft.defaultPlatforms).length > 0;

  if (draft.mode === "periodic_monitoring") {
    if (!draft.scheduleIntent) {
      issues.push(issue("planner-schedule-cadence", "请选择监测周期"));
      issues.push(issue("planner-schedule-timezone", "请填写时区"));
    } else if (!normalizedText(draft.scheduleIntent.timezone)) {
      issues.push(issue("planner-schedule-timezone", "请填写时区"));
    }
    draft.scopes.forEach((scope, index) => {
      if (
        !defaultsHavePlatform &&
        scope.platforms.length === 0 &&
        normalizePlannerList(scope.seedUrls).length === 0
      ) {
        issues.push(
          issue(
            `planner-scope-${index}-platforms`,
            "请选择平台，或提供 Seed URL 交由后端分类",
          ),
        );
      }
    });
  } else {
    if (draft.scheduleIntent !== null) {
      issues.push(issue("planner-schedule-cadence", "批量研究不接受调度配置"));
    }
    draft.scopes.forEach((scope, index) => {
      if (
        hasScopeQueryInput(scope) &&
        !defaultsHavePlatform &&
        scope.platforms.length === 0
      ) {
        issues.push(
          issue(
            `planner-scope-${index}-platforms`,
            "关键词或账号输入需要至少一个平台",
          ),
        );
      }
    });
  }

  const requiredFields = normalizePlannerList(draft.requiredFields);
  const optionalFields = normalizePlannerList(draft.optionalFields);
  const requiredKeys = new Set(requiredFields.map(comparisonKey));
  if (optionalFields.some((field) => requiredKeys.has(comparisonKey(field)))) {
    issues.push(
      issue("planner-optional-fields", "Required 与 Optional Fields 不能重叠"),
    );
  }

  if (draft.budgetCeiling) {
    const amount = Number(draft.budgetCeiling.amount);
    if (
      !normalizedText(draft.budgetCeiling.amount) ||
      !Number.isFinite(amount) ||
      amount < 0
    ) {
      issues.push(issue("planner-amount", "预算必须是非负数"));
    }
  }
  if (
    draft.rateLimitIntent &&
    (!Number.isInteger(draft.rateLimitIntent.maxRequests) ||
      draft.rateLimitIntent.maxRequests < 1)
  ) {
    issues.push(issue("planner-max-requests", "请求数必须是正整数"));
  }
  if (
    draft.rateLimitIntent &&
    (!Number.isInteger(draft.rateLimitIntent.periodSeconds) ||
      draft.rateLimitIntent.periodSeconds < 1)
  ) {
    issues.push(issue("planner-period-seconds", "周期秒数必须是正整数"));
  }
  if (
    draft.retentionIntent &&
    (!Number.isInteger(draft.retentionIntent.days) ||
      draft.retentionIntent.days < 1 ||
      draft.retentionIntent.days > 3650)
  ) {
    issues.push(issue("planner-days", "保留天数必须在 1 到 3650 之间"));
  }
  return issues;
}

export function validatePlannerStep(
  draft: WorkflowPlannerDraft,
  step: PlannerStep,
): PlannerFieldIssue[] {
  if (step === "mode") {
    return validateModeStep(draft);
  }
  if (step === "scopes") {
    return validateScopeStep(draft);
  }
  if (step === "constraints") {
    return validateConstraintStep(draft);
  }
  return [];
}

export function plannerIssuesToFieldErrors(
  issues: readonly PlannerFieldIssue[],
): PlannerFieldErrors {
  const errors: PlannerFieldErrors = {};
  for (const fieldIssue of issues) {
    if (!(fieldIssue.fieldId in errors)) {
      errors[fieldIssue.fieldId] = fieldIssue.message;
    }
  }
  return errors;
}

export function plannerFieldErrorId(fieldId: string): string {
  return `${fieldId}-error`;
}

export function plannerStepForFieldId(fieldId: string): PlannerStep {
  if (fieldId === "planner-scopes" || fieldId.startsWith("planner-scope-")) {
    return "scopes";
  }
  if (fieldId === "planner-mode" || fieldId === "planner-purpose") {
    return "mode";
  }
  return "constraints";
}

function normalizedScope(
  scope: MonitoringScopeFormDraft,
): MonitoringScopeDraft {
  return {
    scopeRef: normalizedText(scope.scopeRef),
    scopeType: scope.scopeType,
    canonicalTerm: normalizedText(scope.canonicalTerm ?? "") || null,
    aliases: normalizePlannerList(scope.aliases),
    includeTerms: normalizePlannerList(scope.includeTerms),
    excludeTerms: normalizePlannerList(scope.excludeTerms),
    officialAccounts: normalizePlannerList(scope.officialAccounts),
    seedUrls: normalizePlannerList(scope.seedUrls),
    languages: normalizePlannerList(scope.languages),
    regions: normalizePlannerList(scope.regions),
    platforms: uniqueValues(scope.platforms),
    matchMode: scope.matchMode,
  };
}

export function buildPlanningInput(draft: WorkflowPlannerDraft): PlanningInput {
  const issues = [
    ...validateModeStep(draft),
    ...validateScopeStep(draft),
    ...validateConstraintStep(draft),
  ];
  if (issues.length > 0) {
    throw new Error(
      `Planner draft is invalid: ${issues
        .map((fieldIssue) => fieldIssue.fieldId)
        .join(", ")}`,
    );
  }

  const base = {
    scopes: draft.scopes.map(normalizedScope),
    defaultLanguages: normalizePlannerList(draft.defaultLanguages),
    defaultRegions: normalizePlannerList(draft.defaultRegions),
    defaultPlatforms: uniqueValues(draft.defaultPlatforms),
    deliveryIntent: draft.deliveryIntent
      ? { outputs: uniqueValues(draft.deliveryIntent.outputs) }
      : null,
    policyProfile: "market_monitoring_balanced" as const,
    purpose: draft.purpose,
    requiredFields: normalizePlannerList(draft.requiredFields),
    optionalFields: normalizePlannerList(draft.optionalFields),
    budgetCeiling: draft.budgetCeiling
      ? {
          amount: normalizedText(draft.budgetCeiling.amount),
          currency: "USD" as const,
        }
      : null,
    rateLimitIntent: draft.rateLimitIntent
      ? { ...draft.rateLimitIntent }
      : null,
    retentionIntent: draft.retentionIntent
      ? { ...draft.retentionIntent }
      : null,
    allowPartialDegradation: draft.allowPartialDegradation,
  };

  if (draft.mode === "periodic_monitoring") {
    if (!draft.scheduleIntent) {
      throw new Error("Planner draft is invalid: planner-schedule-cadence");
    }
    return {
      ...base,
      flowMode: draft.mode,
      scheduleIntent: {
        cadence: draft.scheduleIntent.cadence,
        timezone: normalizedText(draft.scheduleIntent.timezone),
      },
    };
  }

  return { ...base, flowMode: draft.mode };
}
