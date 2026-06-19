export type BrowserDiagnosticRecommendedPath =
  | "generic_web"
  | "browser_automation"
  | "official_api_or_file"
  | "manual_review"
  | "blocked_review";

export type BrowserDiagnosticFit = "high" | "medium" | "low" | "blocked";
export type BrowserDiagnosticFieldStability = "high" | "medium" | "low";

export type BrowserDiagnosticStrategy = {
  recommendedPath: BrowserDiagnosticRecommendedPath;
  fit: BrowserDiagnosticFit;
  confidence: number;
  fieldStability: BrowserDiagnosticFieldStability;
  reasons: string[];
  nextSteps: string[];
  cleaningNotes: string[];
};

export type BrowserDiagnosticRunPolicy = {
  authorizationConfirmed: boolean;
  executionMode: string;
  productionWrite: boolean;
  loginOrPrivatePageAllowed: boolean;
  cookiesExported: boolean;
  note: string | null;
};

export type BrowserDiagnosticVisibleText = {
  length: number;
  lineCount: number;
  sample: string;
};

export type BrowserDiagnosticCounters = {
  links: number;
  sameOriginLinks: number;
  externalLinks: number;
  forms: number;
  inputs: number;
  buttons: number;
  tables: number;
  lists: number;
  articles: number;
  cards: number;
  images: number;
  scripts: number;
  stylesheets: number;
  jsonLdBlocks: number;
};

export type BrowserDiagnosticApiCandidate = {
  url: string;
  initiatorType: string;
  sameOrigin: boolean;
  durationMs: number;
  transferSize: number;
};

export type BrowserDiagnosticNetworkSummary = {
  resourceCount: number;
  sameOriginResources: number;
  crossOriginResources: number;
  xhrFetchCount: number;
  scriptCount: number;
  imageCount: number;
  apiCandidateCount: number;
  apiCandidates: BrowserDiagnosticApiCandidate[];
  initiatorTypeCounts: Record<string, number>;
};

export type BrowserDiagnosticEvidence = {
  screenshotPath: string | null;
  source: string;
  errors: string[];
};

export type BrowserDiagnosticActionReadiness = "ready" | "review" | "blocked";

export type BrowserDiagnosticFieldContractField = {
  key: string;
  label: string;
  valueSample: string;
  source: string;
  required: boolean;
  stability: BrowserDiagnosticFieldStability;
  selectorHint: string;
};

export type BrowserDiagnosticCleaningRule = {
  field: string;
  operation: string;
  description: string;
};

export type BrowserDiagnosticFieldContractDraft = {
  title: string;
  sourceUrl: string;
  fields: BrowserDiagnosticFieldContractField[];
  cleaningRules: BrowserDiagnosticCleaningRule[];
  evidenceSummary: string[];
};

export type BrowserDiagnosticToolRecommendation = {
  toolFamily: BrowserDiagnosticRecommendedPath;
  toolLabel: string;
  collectorType: string;
  fit: BrowserDiagnosticFit;
  riskLevel: "low" | "medium" | "high";
  reason: string;
  nextActions: string[];
};

export type BrowserDiagnosticSourceDraft = {
  type: "generic_web";
  suggestedName: string;
  url: string;
  config: {
    url: string;
    extract_mode: "main_content";
    fields: string[];
    browser_diagnostic: {
      schema_version: "browser_structure_diagnostic.v1";
      final_url: string;
      recommended_path: BrowserDiagnosticRecommendedPath;
      confidence: number;
      field_stability: BrowserDiagnosticFieldStability;
      evidence_source: string;
      screenshot_path: string | null;
    };
    field_contract: {
      fields: Array<{
        key: string;
        label: string;
        source: string;
        required: boolean;
      }>;
      cleaning_rules: BrowserDiagnosticCleaningRule[];
    };
  };
};

export type BrowserDiagnosticActionPlan = {
  readiness: BrowserDiagnosticActionReadiness;
  canCreateGenericWebSource: boolean;
  fieldContract: BrowserDiagnosticFieldContractDraft;
  primaryRecommendation: BrowserDiagnosticToolRecommendation;
  secondaryRecommendations: BrowserDiagnosticToolRecommendation[];
  sourceDraft: BrowserDiagnosticSourceDraft | null;
  blockingReasons: string[];
  riskControls: string[];
};

export type BrowserStructureDiagnostic = {
  schemaVersion: "browser_structure_diagnostic.v1";
  generatedAt: string;
  requestedUrl: string;
  finalUrl: string;
  runPolicy: BrowserDiagnosticRunPolicy;
  visibleText: BrowserDiagnosticVisibleText;
  domCounters: BrowserDiagnosticCounters;
  riskFlags: string[];
  extractionStrategy: BrowserDiagnosticStrategy;
  networkSummary: BrowserDiagnosticNetworkSummary;
  evidence: BrowserDiagnosticEvidence;
};
