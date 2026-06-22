import type { AlertEvent } from "@/types/alert";
import type { NotificationItem } from "@/types/notification";
import type { Report } from "@/types/report";
import type { Signal } from "@/types/signal";

export type AutomationFieldCandidate = {
  key: string;
  label: string;
  value: string | number | boolean | null;
  dataType: string;
  source: string;
  confidence: number;
  selected: boolean;
  cleaningRule: string;
};

export type AutomationToolRecommendation = {
  tool: string;
  collectorType: string;
  fit: string;
  riskLevel: string;
  reason: string;
};

export type AutomationCleaningStep = {
  field: string;
  operation: string;
  description: string;
};

export type AutomationSourceDraft = {
  type: string;
  config: Record<string, unknown>;
  suggestedName: string;
  scheduleCron: string | null;
};

export type AutomationPlatformPackageField = {
  key: string;
  label: string;
  dataType: string;
  required: boolean;
  source: string;
  cleaningRule: string;
};

export type AutomationPlatformPackageSampleUrl = {
  label: string;
  entrypoint: "product-discovery" | "site-analysis" | "sop-import" | "source-create" | "preflight";
  url: string;
  description: string;
};

export type AutomationPlatformPackageCleaningRule = AutomationCleaningRule & {
  description: string;
};

export type AutomationPlatformPackageStrategy = {
  id: string;
  label: string;
  entrypoint: string;
  collectorType: string;
  fit: "high" | "medium" | "low";
  canStartFromAutomation: boolean;
  reviewRequired: boolean;
  description: string;
};

export type AutomationPlatformPackageRiskBoundary = {
  condition: string;
  severity: "info" | "warning" | "blocked";
  guidance: string;
};

export type AutomationPlatformPackageSopLink = {
  label: string;
  href: string;
};

export type AutomationPlatformPackageFixture = {
  fixtureType: string;
  available: boolean;
  description: string;
};

export type AutomationPlatformPackage = {
  id: string;
  name: string;
  category: string;
  summary: string;
  supportedTargets: string[];
  collectorTypes: string[];
  fieldSchema: AutomationPlatformPackageField[];
  defaultEntrypoint: "product-discovery" | "site-analysis" | "sop-import" | "source-create" | "preflight";
  sampleUrls: AutomationPlatformPackageSampleUrl[];
  cleaningRules: AutomationPlatformPackageCleaningRule[];
  operatorChecklist: string[];
  strategyMatrix: AutomationPlatformPackageStrategy[];
  riskBoundaries: AutomationPlatformPackageRiskBoundary[];
  sopLinks: AutomationPlatformPackageSopLink[];
  sampleFixture: AutomationPlatformPackageFixture;
  executionBoundary: "executable" | "sop_import_only" | "blocked";
  runStarted: boolean;
};

export type AutomationPlatformPackageList = {
  items: AutomationPlatformPackage[];
  total: number;
  runStarted: boolean;
};

export type AutomationCapabilityProbeBackendCandidate = {
  backendId: string;
  label: string;
  priority: number;
  status:
    | "available"
    | "missing_tool"
    | "not_configured"
    | "requires_login"
    | "requires_proxy"
    | "manual_review"
    | "blocked"
    | "unknown";
  credentialMode: "none" | "token" | "cookie" | "browser_profile" | "manual_export" | "unknown";
  requiresLogin: boolean;
  requiresProxy: boolean;
  evidenceLevel:
    | "L0-unverified"
    | "L1-repo-or-runtime"
    | "L2-fixture-or-dry-run"
    | "L3-production-read-only"
    | "L4-authorized-live";
  notes: string[];
};

export type AutomationAgentReachChannelProbe = {
  schemaVersion: "agent_reach_channel_probe.v1";
  installed: boolean;
  commandPath: string | null;
  doctorStatus:
    | "available"
    | "missing_tool"
    | "not_configured"
    | "requires_login"
    | "requires_proxy"
    | "blocked"
    | "unknown";
  activeBackend: string | null;
  requiresLogin: boolean;
  requiresProxy: boolean;
  blockedReason: string | null;
  platforms: string[];
  readInvoked: boolean;
  searchInvoked: boolean;
  rawSummary: Record<string, unknown>;
};

export type AutomationCapabilityProbe = {
  schemaVersion: "capability_probe.v1";
  platformId: string;
  platformLabel: string;
  generatedAt: string;
  doctorStatus:
    | "available"
    | "missing_tool"
    | "not_configured"
    | "requires_login"
    | "requires_proxy"
    | "manual_review"
    | "blocked"
    | "unknown";
  credentialMode: "none" | "token" | "cookie" | "browser_profile" | "manual_export" | "unknown";
  executionBoundary: "executable" | "read_only_probe" | "import_only" | "sop_only" | "blocked";
  riskLevel: "low" | "medium" | "high";
  backendCandidates: AutomationCapabilityProbeBackendCandidate[];
  agentReach: AutomationAgentReachChannelProbe | null;
  allowedOutputs: string[];
  forbiddenActions: string[];
  nextActions: string[];
  runStarted: boolean;
  collectionResourcesWritten: boolean;
};

export type AutomationCapabilityProbeList = {
  schemaVersion: "capability_probe_list.v1";
  generatedAt: string;
  items: AutomationCapabilityProbe[];
  total: number;
  runStarted: boolean;
  collectionResourcesWritten: boolean;
};

export type AutomationExtractionPlan = {
  id: string;
  siteAnalysisId: string;
  projectId: string;
  name: string;
  versionNumber: number;
  collectorType: string;
  selectedFields: string[];
  sourceDraft: AutomationSourceDraft;
  scheduleCron: string | null;
  status: string;
  riskLevel: string;
  auditEvents: Array<Record<string, unknown>>;
  createdAt: string;
  runStarted: boolean;
};

export type AutomationSiteAnalysisHistoryItem = {
  id: string;
  projectId: string;
  requestedUrl: string;
  target: string;
  status: string;
  platformType: string;
  pageType: string;
  riskLevel: string;
  analyzedAt: string;
  createdAt: string;
  latestPlan: AutomationExtractionPlan | null;
};

export type AutomationSiteAnalysisList = {
  items: AutomationSiteAnalysisHistoryItem[];
  total: number;
  runStarted: boolean;
};

export type AutomationSiteAnalysisListInput = {
  projectId?: string;
  target?: "ecommerce_product" | "browser_automation";
  limit?: number;
};

export type AutomationSiteAnalysis = {
  requestedUrl: string;
  analyzedAt: string;
  authorizationConfirmed: boolean;
  platformProfile: {
    platformType: string;
    confidence: number;
    indicators: string[];
    riskLevel: string;
  };
  pageStructure: {
    pageType: string;
    title: string | null;
    canonicalUrl: string | null;
    scriptCount: number;
    formCount: number;
    imageCount: number;
    productSchemaCount: number;
    sameOriginLinkCount: number;
    textSample: string;
  };
  fieldCandidates: AutomationFieldCandidate[];
  toolRecommendations: AutomationToolRecommendation[];
  cleaningPlan: AutomationCleaningStep[];
  sourceDraft: AutomationSourceDraft;
  blockedReasons: string[];
  siteAnalysis: AutomationSiteAnalysisHistoryItem | null;
  extractionPlan: AutomationExtractionPlan | null;
  siteAnalysisCreated: boolean;
  extractionPlanCreated: boolean;
  runStarted: boolean;
};

export type AutomationSiteAnalysisInput = {
  projectId?: string;
  url: string;
  authorized: boolean;
  target?: "ecommerce_product";
  fields?: string[];
};

export type AutomationBrowserFieldContractFieldInput = {
  key: string;
  label: string;
  source: string;
  required: boolean;
  selected: boolean;
  selectorHint?: string | null;
};

export type AutomationBrowserCleaningRuleInput = {
  field: string;
  operation: string;
  description: string;
};

export type AutomationBrowserAutomationPlanInput = {
  projectId: string;
  requestedUrl: string;
  authorized: boolean;
  name?: string;
  runner: "browser_harness";
  executionMode: "read_only_browser_harness";
  riskLevel: "low" | "medium" | "high";
  fieldContract: {
    fields: AutomationBrowserFieldContractFieldInput[];
    cleaningRules: AutomationBrowserCleaningRuleInput[];
  };
  browserDiagnostic: {
    schemaVersion: "browser_structure_diagnostic.v1";
    finalUrl: string;
    recommendedPath: string;
    confidence: number;
    fieldStability?: "high" | "medium" | "low" | null;
    evidenceSource: string;
    screenshotPath?: string | null;
  };
  diagnosticPayload?: Record<string, unknown>;
  apiCandidates: string[];
  guardrails: string[];
};

export type AutomationBrowserDiagnosticRun = {
  id: string;
  projectId: string;
  siteAnalysisId: string | null;
  requestedUrl: string;
  finalUrl: string;
  status: string;
  authorizationConfirmed: boolean;
  schemaVersion: string;
  recommendedPath: string;
  confidence: number;
  fieldStability: string | null;
  evidenceSource: string;
  screenshotPath: string | null;
  runPolicy: Record<string, unknown>;
  pageSummary: Record<string, unknown>;
  networkSummary: Record<string, unknown>;
  accessibilitySummary: Record<string, unknown>;
  riskFlags: Array<Record<string, unknown>>;
  extractionStrategy: Record<string, unknown>;
  blockedReasons: string[];
  createdAt: string;
  runStarted: boolean;
};

export type AutomationBrowserDiagnosticRunList = {
  items: AutomationBrowserDiagnosticRun[];
  total: number;
  runStarted: boolean;
};

export type AutomationBrowserAutomationPlan = {
  siteAnalysis: AutomationSiteAnalysisHistoryItem;
  extractionPlan: AutomationExtractionPlan;
  browserDiagnostic: AutomationBrowserDiagnosticRun;
  siteAnalysisCreated: boolean;
  extractionPlanCreated: boolean;
  browserDiagnosticCreated: boolean;
  runStarted: boolean;
};

export type AutomationBrowserExecutableSpecDryRunInput = {
  authorized: boolean;
  confirmReview: boolean;
  siteAnalysisId: string;
  extractionPlanId: string;
  browserDiagnosticRunId?: string | null;
};

export type AutomationBrowserExecutableSpecCheck = {
  key: string;
  label: string;
  status: "passed" | "review" | "blocked";
  message: string;
  evidence: Record<string, unknown>;
};

export type AutomationBrowserExecutableSpecDryRunSummary = {
  status: "ready" | "review" | "blocked";
  totalChecks: number;
  passedChecks: number;
  reviewChecks: number;
  blockedChecks: number;
  selectorCount: number;
  waitConditionCount: number;
  apiCandidateCount: number;
  manualReviewRequired: boolean;
  canDryRunAfterReview: boolean;
  writeAllowed: boolean;
  runStarted: boolean;
};

export type AutomationBrowserExecutableSpecDryRun = {
  siteAnalysis: AutomationSiteAnalysisHistoryItem;
  extractionPlan: AutomationExtractionPlan;
  browserDiagnostic: AutomationBrowserDiagnosticRun | null;
  summary: AutomationBrowserExecutableSpecDryRunSummary;
  checks: AutomationBrowserExecutableSpecCheck[];
  executableSpec: Record<string, unknown>;
  blockedReasons: string[];
  auditEvents: Array<Record<string, unknown>>;
  runStarted: boolean;
};

export type AutomationBrowserDiagnosticJobCreateInput = {
  authorized: boolean;
  confirmCreate: boolean;
  siteAnalysisId: string;
  extractionPlanId: string;
  browserDiagnosticRunId?: string | null;
  networkObservationMode?: "metadata_only" | "same_origin_api_candidates";
  artifactMode?: "none" | "screenshot_reference_only" | "diagnostic_json_reference";
  note?: string | null;
};

export type AutomationBrowserDiagnosticJob = {
  id: string;
  projectId: string;
  siteAnalysisId: string;
  extractionPlanId: string;
  browserDiagnosticRunId: string;
  requestedUrl: string;
  finalUrl: string;
  status: string;
  authorizationConfirmed: boolean;
  runner: string;
  executionMode: string;
  selectorScope: Array<Record<string, unknown>>;
  waitPolicy: Array<Record<string, unknown>>;
  networkObservationPolicy: Record<string, unknown>;
  artifactPolicy: Record<string, unknown>;
  safetyFlags: string[];
  dryRunSummary: Record<string, unknown>;
  executableSpecSnapshot: Record<string, unknown>;
  blockedReasons: string[];
  auditEvents: Array<Record<string, unknown>>;
  createdAt: string;
  updatedAt: string;
  cancelledAt: string | null;
  runStarted: boolean;
};

export type AutomationBrowserDiagnosticJobList = {
  items: AutomationBrowserDiagnosticJob[];
  total: number;
  runStarted: boolean;
};

export type AutomationBrowserExecutorContractInput = {
  authorized: boolean;
  confirmReview: boolean;
  artifactRetentionDays?: number;
  maxPreviewRows?: number;
  includeScreenshot?: boolean;
  includeTraceSummary?: boolean;
  includeHarSummary?: boolean;
  note?: string | null;
};

export type AutomationBrowserExecutorReadinessCheck = {
  key: string;
  label: string;
  status: "passed" | "review" | "blocked";
  message: string;
  evidence: Record<string, unknown>;
};

export type AutomationBrowserExecutorContract = {
  job: AutomationBrowserDiagnosticJob;
  adapter: Record<string, unknown>;
  runtimeIsolation: Record<string, unknown>;
  artifactRetentionPolicy: Record<string, unknown>;
  allowedActions: string[];
  deniedActions: string[];
  readinessChecks: AutomationBrowserExecutorReadinessCheck[];
  blockedReasons: string[];
  auditEvents: Array<Record<string, unknown>>;
  runStarted: boolean;
  executionStarted: boolean;
};

export type AutomationBrowserLocalRunnerInput = {
  authorized: boolean;
  confirmExecute: boolean;
  runMode?: "diagnostic_snapshot_replay" | "ephemeral_browser_harness_probe";
  confirmRealBrowserProbe?: boolean;
  browserHarnessBinary?: string;
  probeTimeoutSeconds?: number;
  artifactRetentionDays?: number;
  maxPreviewRows?: number;
  includeScreenshot?: boolean;
  includeTraceSummary?: boolean;
  includeHarSummary?: boolean;
  note?: string | null;
};

export type AutomationBrowserLocalRunnerResult = {
  id: string;
  job: AutomationBrowserDiagnosticJob;
  status: string;
  runner: string;
  runMode: string;
  contractSnapshot: Record<string, unknown>;
  artifactManifest: Record<string, unknown>;
  selectorResults: Array<Record<string, unknown>>;
  selectorEvaluations: Array<Record<string, unknown>>;
  previewRows: Array<Record<string, unknown>>;
  networkObservationSummary: Record<string, unknown>;
  networkMetadataSummary: Record<string, unknown>;
  errorSummary: Record<string, unknown>;
  promotionGate: Record<string, unknown>;
  redactionSummary: Record<string, unknown>;
  blockedReasons: string[];
  auditEvents: Array<Record<string, unknown>>;
  createdAt: string;
  updatedAt: string;
  startedAt: string;
  finishedAt: string;
  executionStarted: boolean;
  browserStarted: boolean;
  filesWritten: boolean;
  collectionResourcesWritten: boolean;
};

export type AutomationBrowserLocalRunnerResultList = {
  items: AutomationBrowserLocalRunnerResult[];
  total: number;
  browserStarted: boolean;
  filesWritten: boolean;
  collectionResourcesWritten: boolean;
};

export type AutomationProductCandidate = {
  url: string;
  title: string | null;
  source: string;
  confidence: number;
  canonicalUrl: string;
};

export type AutomationProductDiscovery = {
  requestedUrl: string;
  analyzedAt: string;
  authorizationConfirmed: boolean;
  platformProfile: {
    platformType: string;
    confidence: number;
    indicators: string[];
    riskLevel: string;
  };
  pageStructure: {
    pageType: string;
    title: string | null;
    canonicalUrl: string | null;
    linkCount: number;
    productLinkCount: number;
    jsonldUrlCount: number;
    sitemapUrlCount: number;
    paginationUrlCount: number;
    duplicateUrlCount: number;
    skippedUrlCount: number;
    scriptCount: number;
    textSample: string;
  };
  productCandidates: AutomationProductCandidate[];
  toolRecommendations: AutomationToolRecommendation[];
  discoveryPlan: {
    nextCollectorType: string;
    candidateCount: number;
    maxProducts: number;
    fanOutRequiresReview: boolean;
    paginationUrls: string[];
    dedupeSummary: {
      inputUrlCount: number;
      canonicalCandidateCount: number;
      duplicateUrlCount: number;
      skippedUrlCount: number;
      skippedReasons: string[];
    };
  };
  sourceDraft: {
    type: string;
    config: Record<string, unknown>;
    suggestedName: string;
    scheduleCron: string | null;
  };
  blockedReasons: string[];
};

export type AutomationProductDiscoveryInput = {
  url: string;
  authorized: boolean;
  maxProducts?: number;
};

export type AutomationFanoutCandidateInput = {
  url: string;
  title?: string | null;
  source?: string | null;
  confidence?: number | null;
};

export type AutomationFanoutCandidateStatus = {
  url: string;
  title: string | null;
  source: string | null;
  confidence: number | null;
  status: "ready" | "blocked";
  reason: string | null;
};

export type AutomationProductFanoutPreview = {
  requestedParentUrl: string;
  analyzedAt: string;
  authorizationConfirmed: boolean;
  candidateStatuses: AutomationFanoutCandidateStatus[];
  sourceDrafts: Array<{
    type: string;
    config: Record<string, unknown>;
    suggestedName: string;
    scheduleCron: string | null;
  }>;
  batchPlan: {
    runMode: "preview_only";
    nextCollectorType: string;
    readyCount: number;
    blockedCount: number;
    maxSources: number;
    fields: string[];
    manualReviewRequired: boolean;
    executionBoundary: string;
  };
  blockedReasons: string[];
};

export type AutomationProductFanoutPreviewInput = {
  parentUrl: string;
  authorized: boolean;
  candidates: AutomationFanoutCandidateInput[];
  fields?: string[];
  maxSources?: number;
};

export type AutomationPersistedFanoutSource = {
  url: string;
  action: "created" | "reused";
  source: {
    id: string;
    projectId: string;
    name: string;
    type: string;
    url: string | null;
    enabled: boolean;
    config: Record<string, unknown>;
    scheduleCron: string | null;
    createdAt: string;
    updatedAt: string;
  };
  task: {
    id: string;
    sourceId: string;
    collectorType: string;
    name: string;
    status: string;
    scheduleCron: string | null;
  } | null;
};

export type AutomationProductFanoutCreate = {
  requestedParentUrl: string;
  createdAt: string;
  authorizationConfirmed: boolean;
  persistedSources: AutomationPersistedFanoutSource[];
  candidateStatuses: AutomationFanoutCandidateStatus[];
  summary: {
    createdSources: number;
    reusedSources: number;
    enabledTasks: number;
    blockedCandidates: number;
    runStarted: boolean;
  };
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationProductFanoutCreateInput = AutomationProductFanoutPreviewInput & {
  projectId: string;
  enableTasks?: boolean;
};

export type AutomationProductBatchFieldCompleteness = {
  configuredFields: string[];
  extractedFields: string[];
  missingFields: string[];
  fieldValues: Record<string, unknown>;
  completenessRatio: number;
  completenessPercent: number;
};

export type AutomationProductBatchRunItem = {
  taskId: string;
  taskName: string | null;
  sourceId: string | null;
  sourceUrl: string | null;
  status: "run_completed" | "run_failed" | "blocked";
  blockedReason: string | null;
  run: {
    id: string;
    taskId: string;
    status: string;
    recordsCount: number;
    entitiesCount: number;
    errorMessage: string | null;
    startedAt: string | null;
    finishedAt: string | null;
  } | null;
  recordsCount: number;
  entitiesCount: number;
  fieldCompleteness: AutomationProductBatchFieldCompleteness | null;
  errorMessage: string | null;
};

export type AutomationProductBatchRun = {
  createdAt: string;
  authorizationConfirmed: boolean;
  items: AutomationProductBatchRunItem[];
  summary: {
    requestedTasks: number;
    runTasks: number;
    blockedTasks: number;
    successfulRuns: number;
    failedRuns: number;
    recordsCount: number;
    entitiesCount: number;
    averageCompletenessPercent: number;
    runStarted: boolean;
  };
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationProductBatchRunInput = {
  authorized: boolean;
  taskIds: string[];
  maxTasks?: number;
};

export type AutomationProductDatasetRow = {
  rowId: string;
  taskRunId: string;
  rawRecordId: string;
  sourceUrl: string | null;
  values: Record<string, unknown>;
  missingFields: string[];
  completenessPercent: number;
};

export type AutomationProductDatasetPreview = {
  createdAt: string;
  authorizationConfirmed: boolean;
  rows: AutomationProductDatasetRow[];
  summary: {
    requestedRuns: number;
    matchedRuns: number;
    rowsCount: number;
    selectedFields: string[];
    averageCompletenessPercent: number;
    exportFormat: "json";
    exportReady: boolean;
  };
  cleaningScriptDraft: string[];
  exportPreview: Record<string, unknown>;
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationProductDatasetPreviewInput = {
  authorized: boolean;
  taskRunIds: string[];
  fields?: string[];
  maxRows?: number;
};

export type AutomationCleaningRule = {
  field: string;
  operation:
    | "strip_text"
    | "parse_decimal"
    | "normalize_url"
    | "uppercase"
    | "normalize_availability"
    | "fill_default";
  value?: string | number | boolean | null;
  description?: string | null;
};

export type AutomationCleaningPlanDryRunRow = {
  rowId: string;
  taskRunId: string;
  rawRecordId: string;
  sourceUrl: string | null;
  beforeValues: Record<string, unknown>;
  afterValues: Record<string, unknown>;
  missingFieldsBefore: string[];
  missingFieldsAfter: string[];
  changedFields: string[];
};

export type AutomationCleaningPlanDryRun = {
  createdAt: string;
  authorizationConfirmed: boolean;
  rows: AutomationCleaningPlanDryRunRow[];
  summary: {
    rowsCount: number;
    rowsChanged: number;
    rulesCount: number;
    selectedFields: string[];
    datasetVersionCreated: boolean;
    cleaningPlanCreated: boolean;
    runStarted: boolean;
  };
  cleaningScript: string[];
  exportPreview: Record<string, unknown>;
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationCleaningPlan = {
  id: string;
  projectId: string;
  name: string;
  versionNumber: number;
  target: string;
  selectedFields: string[];
  sourceTaskRunIds: string[];
  rules: Array<Record<string, unknown>>;
  cleaningScript: string[];
  dryRunPreview: Record<string, unknown>;
  status: string;
  createdAt: string;
};

export type AutomationCleaningPlanCreate = {
  savedAt: string;
  authorizationConfirmed: boolean;
  cleaningPlan: AutomationCleaningPlan;
  dryRun: AutomationCleaningPlanDryRun;
  cleaningPlanCreated: boolean;
  datasetVersionCreated: boolean;
  runStarted: boolean;
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationCleaningPlanInput = AutomationProductDatasetPreviewInput & {
  rules: AutomationCleaningRule[];
};

export type AutomationCleaningPlanCreateInput = AutomationCleaningPlanInput & {
  name: string;
};

export type AutomationDataset = {
  id: string;
  projectId: string;
  name: string;
  datasetType: string;
  status: string;
  description: string | null;
};

export type AutomationDatasetVersion = {
  id: string;
  datasetId: string;
  cleaningPlanId: string | null;
  versionNumber: number;
  sourceTaskRunIds: string[];
  selectedFields: string[];
  cleaningScript: string[];
  rowCount: number;
  averageCompletenessPercent: number;
  status: string;
  createdAt: string;
  exportPreview: Record<string, unknown>;
};

export type AutomationDatasetExportFormat = "csv" | "json" | "jsonl";

export type AutomationProductDatasetExportJob = {
  id: string;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  exportFormat: AutomationDatasetExportFormat;
  status: string;
  filename: string;
  contentType: string;
  artifactSizeBytes: number;
  rowCount: number;
  checksumSha256: string;
  errorMessage: string | null;
  createdAt: string;
  finishedAt: string | null;
  downloadUrl: string | null;
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationProductDatasetExportCreateInput = {
  authorized: boolean;
  confirmCreate: boolean;
  datasetId: string;
  datasetVersionId: string;
  exportFormat: AutomationDatasetExportFormat;
};

export type AutomationProductDatasetExportList = {
  items: AutomationProductDatasetExportJob[];
  total: number;
  exportCreated: boolean;
  runStarted: boolean;
};

export type AutomationProductDatasetExportListInput = {
  datasetId: string;
  datasetVersionId?: string;
  limit?: number;
};

export type AutomationProductDatasetSave = {
  savedAt: string;
  authorizationConfirmed: boolean;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationProductDatasetSaveInput = AutomationProductDatasetPreviewInput & {
  name: string;
  description?: string;
  cleaningPlanId?: string;
};

export type AutomationScheduleApprovedTask = {
  taskId: string;
  taskName: string;
  status: string;
  scheduleCron: string | null;
  schedulePolicy: string;
  freshnessTargetHours: number;
  datasetId: string;
  datasetVersionId: string;
  approvedAt: string;
};

export type AutomationScheduleBlockedTask = {
  taskId: string;
  reason: string;
};

export type AutomationProductScheduleApprove = {
  approvedAt: string;
  authorizationConfirmed: boolean;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  approvedTasks: AutomationScheduleApprovedTask[];
  blockedTasks: AutomationScheduleBlockedTask[];
  summary: {
    requestedTasks: number;
    approvedTasks: number;
    blockedTasks: number;
    runStarted: boolean;
  };
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationProductScheduleApproveInput = {
  authorized: boolean;
  datasetId: string;
  datasetVersionId: string;
  taskIds: string[];
  schedulePolicy?: "auto_freshness" | "manual_refresh_only";
  scheduleCron?: string | null;
  freshnessTargetHours?: number;
  minimumCompletenessPercent?: number;
  note?: string;
};

export type AutomationProductDriftItem = {
  taskId: string;
  taskName: string | null;
  sourceUrl: string | null;
  status: "ok" | "warning" | "critical" | "blocked";
  blockedReason: string | null;
  latestRunId: string | null;
  latestRunStatus: string | null;
  datasetVersionCompletenessPercent: number;
  latestCompletenessPercent: number | null;
  completenessDropPercent: number | null;
  missingFields: string[];
  newMissingFields: string[];
  freshnessTargetHours: number | null;
  staleHours: number | null;
  issues: string[];
};

export type AutomationProductDriftCheck = {
  checkedAt: string;
  authorizationConfirmed: boolean;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  items: AutomationProductDriftItem[];
  summary: {
    requestedTasks: number;
    checkedTasks: number;
    blockedTasks: number;
    warningTasks: number;
    criticalTasks: number;
    staleTasks: number;
    missingFieldTasks: number;
    driftLayers: Record<string, number>;
    runStarted: boolean;
    alertCreated: boolean;
  };
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationProductDriftCheckInput = {
  authorized: boolean;
  datasetId: string;
  datasetVersionId: string;
  taskIds: string[];
  completenessDropThresholdPercent?: number;
  freshnessGraceHours?: number;
};

export type AutomationProductDriftEvent = {
  id: string;
  createdAt: string;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  eventType: string;
  status: "ok" | "warning" | "critical" | "blocked";
  thresholds: Record<string, unknown>;
  summary: AutomationProductDriftCheck["summary"];
  items: AutomationProductDriftItem[];
  auditEvents: Array<Record<string, unknown>>;
  note: string | null;
  runStarted: boolean;
  alertCreated: boolean;
};

export type AutomationProductDriftEventSaveInput = AutomationProductDriftCheckInput & {
  note?: string;
};

export type AutomationProductDriftEventList = {
  items: AutomationProductDriftEvent[];
  total: number;
  runStarted: boolean;
  alertCreated: boolean;
};

export type AutomationProductDriftEventListInput = {
  datasetId?: string;
  datasetVersionId?: string;
  limit?: number;
};

export type AutomationGitHubToolReportRepository = {
  repoFullName: string;
  htmlUrl: string | null;
  description: string | null;
  stars: number;
  forks: number | null;
  openIssues: number | null;
  watchers: number | null;
  language: string | null;
  topics: string[];
  licenseSpdxId: string | null;
  defaultBranch: string | null;
  latestReleaseTag: string | null;
  latestReleasePublishedAt: string | null;
  archived: boolean | null;
  fork: boolean | null;
  updatedAt: string | null;
  pushedAt: string | null;
  readmeDetected: boolean | null;
  readmeHtmlUrl: string | null;
  readmeSize: number | null;
  issueActivityOpenCount: number | null;
  issueActivityStatus: string | null;
  commitFreshnessDays: number | null;
  commitFreshnessStatus: string | null;
};

export type AutomationGitHubToolReport = {
  generatedAt: string;
  authorizationConfirmed: boolean;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  summary: {
    repositoryCount: number;
    totalStars: number;
    highValueRepositories: number;
    licensedRepositories: number;
    releaseTaggedRepositories: number;
    readmeDocumentedRepositories: number;
    issueActiveRepositories: number;
    freshCommitRepositories: number;
    archivedRepositories: number;
    forkRepositories: number;
    languages: Record<string, number>;
    topTopics: Record<string, number>;
    reportCreated: boolean;
    runStarted: boolean;
  };
  topRepositories: AutomationGitHubToolReportRepository[];
  recommendations: string[];
  auditEvents: Array<Record<string, unknown>>;
  blockedReasons: string[];
};

export type AutomationGitHubToolReportInput = {
  authorized: boolean;
  datasetId: string;
  datasetVersionId: string;
  minStars?: number;
  topLimit?: number;
};

export type AutomationGitHubToolReportAsset = AutomationGitHubToolReport & {
  report: Report;
  notificationCreated: boolean;
};

export type AutomationGitHubToolReportAssetInput = AutomationGitHubToolReportInput & {
  confirmCreate: boolean;
};

export type AutomationProductDatasetListItem = {
  dataset: AutomationDataset;
  latestVersion: AutomationDatasetVersion | null;
  versionCount: number;
  latestDriftEvent: AutomationProductDriftEvent | null;
  driftEventCount: number;
};

export type AutomationProductDatasetList = {
  items: AutomationProductDatasetListItem[];
  total: number;
  runStarted: boolean;
  alertCreated: boolean;
};

export type AutomationProductDatasetListInput = {
  projectId?: string;
  limit?: number;
};

export type AutomationProductDatasetVersionList = {
  dataset: AutomationDataset;
  versions: AutomationDatasetVersion[];
  total: number;
  runStarted: boolean;
  alertCreated: boolean;
};

export type AutomationProductDatasetVersionListInput = {
  datasetId: string;
  limit?: number;
};

export type AutomationProductDriftAlertRuleDraft = {
  name: string;
  projectId: string;
  signalType: "dataset_drift";
  condition: Record<string, unknown>;
  channel: "in_app" | "email" | "both";
  enabled: boolean;
};

export type AutomationProductDriftAlertSummary = {
  matchedEvents: number;
  criticalEvents: number;
  warningEvents: number;
  alertRuleCreated: boolean;
  signalCreated: boolean;
  alertEventCreated: boolean;
  notificationCreated: boolean;
  runStarted: boolean;
};

export type AutomationProductDriftAlertPreview = {
  generatedAt: string;
  authorizationConfirmed: boolean;
  dataset: AutomationDataset;
  latestVersion: AutomationDatasetVersion | null;
  ruleDraft: AutomationProductDriftAlertRuleDraft;
  matchedEvents: AutomationProductDriftEvent[];
  summary: AutomationProductDriftAlertSummary;
  blockedReasons: string[];
};

export type AutomationProductDriftAlertRuleCreate = AutomationProductDriftAlertPreview & {
  alertRule: {
    id: string;
    workspaceId: string;
    projectId: string | null;
    name: string;
    signalType: string;
    condition: Record<string, unknown>;
    channel: string;
    enabled: boolean;
    createdAt: string;
  };
};

export type AutomationProductDriftAlertPreviewInput = {
  authorized: boolean;
  datasetId: string;
  datasetVersionId?: string | null;
  minStatus?: "warning" | "critical";
  channel?: "in_app" | "email" | "both";
  enabled?: boolean;
  name?: string | null;
  limit?: number;
};

export type AutomationProductDriftAlertRuleCreateInput =
  AutomationProductDriftAlertPreviewInput & {
    confirmCreate: boolean;
  };

export type AutomationProductDriftAlertEventCreate = {
  generatedAt: string;
  authorizationConfirmed: boolean;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  driftEvent: AutomationProductDriftEvent;
  signal: Signal;
  alertEvents: AlertEvent[];
  summary: AutomationProductDriftAlertSummary;
  blockedReasons: string[];
};

export type AutomationProductDriftAlertEventCreateInput = {
  authorized: boolean;
  confirmCreate: boolean;
  datasetId: string;
  datasetVersionId: string;
  driftEventId: string;
};

export type AutomationProductDriftAlertNotificationSend = {
  generatedAt: string;
  authorizationConfirmed: boolean;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  driftEvent: AutomationProductDriftEvent;
  alertEvents: AlertEvent[];
  notifications: NotificationItem[];
  summary: AutomationProductDriftAlertSummary;
  blockedReasons: string[];
};

export type AutomationProductDriftAlertNotificationSendInput = {
  authorized: boolean;
  confirmSend: boolean;
  datasetId: string;
  datasetVersionId: string;
  driftEventId: string;
  alertEventIds: string[];
};

export type AutomationProductDriftAlertEmailDelivery = {
  alertEventId: string;
  recipientEmail: string;
  delivered: boolean;
  deliveredAt: string | null;
  reason: string | null;
};

export type AutomationProductDriftAlertEmailSend = {
  generatedAt: string;
  authorizationConfirmed: boolean;
  dataset: AutomationDataset;
  version: AutomationDatasetVersion;
  driftEvent: AutomationProductDriftEvent;
  alertEvents: AlertEvent[];
  emailDeliveries: AutomationProductDriftAlertEmailDelivery[];
  summary: AutomationProductDriftAlertSummary;
  blockedReasons: string[];
};

export type AutomationProductDriftAlertEmailSendInput = {
  authorized: boolean;
  confirmSend: boolean;
  datasetId: string;
  datasetVersionId: string;
  driftEventId: string;
  alertEventIds: string[];
  recipientEmail?: string;
};
