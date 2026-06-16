export type ToolkitMetrics = {
  sourceCount: number;
  toolCount: number;
  methodCount: number;
  intelligenceCount: number;
  evidenceCount: number;
  lastCollectedAt: string | null;
};

export type ToolkitTool = {
  id: string;
  name: string;
  category: string;
  riskLevel: string;
  collectorType: string;
  sourceTitle: string;
  sourceUrl: string | null;
  description: string | null;
  language: string | null;
  license: string | null;
  stars: number | null;
  forks: number | null;
  openIssues: number | null;
  updatedAt: string | null;
  collectedAt: string;
  sourceCredibilityScore: number;
  sourceCredibilityLevel: string;
  sourceCredibilityFactors: string[];
};

export type ToolkitMethod = {
  id: string;
  title: string;
  category: string;
  riskLevel: string;
  collectorType: string;
  sourceUrl: string | null;
  platform: string | null;
  recommendedCollector: string | null;
  dataTypes: string[];
  boundary: string | null;
  trainingTakeaway: string | null;
  collectedAt: string;
};

export type ToolkitIntelligence = {
  id: string;
  title: string;
  summary: string;
  domain: string;
  intelligenceType: string;
  finalScore: number;
  evidenceCount: number;
  updatedAt: string;
};

export type ToolkitLearningPath = {
  id: string;
  title: string;
  stage: string;
  focus: string;
  riskLevel: string;
  toolCount: number;
  methodCount: number;
  intelligenceCount: number;
  evidenceCount: number;
  tools: string[];
  methods: string[];
  acceptanceCriteria: string[];
  sourceUrls: string[];
};

export type ToolkitLecturePlaybook = {
  id: string;
  intelligenceId: string;
  title: string;
  audience: string;
  level: string;
  durationMinutes: number;
  claim: string;
  teachingSequence: string[];
  handsOnSteps: string[];
  verificationSteps: string[];
  riskBoundaries: string[];
  classroomExercise: string;
  evidenceUrls: string[];
  evidenceCount: number;
  finalScore: number;
};

export type ToolkitImageAnchorDiagnostic = {
  id: string;
  imageLabel: string;
  extractedClaim: string;
  sourceTitle: string;
  sourceUrl: string;
  sourceType: string;
  classification: string;
  riskLevel: string;
  valueJudgement: string;
  collectionUse: string;
  trainingTakeaway: string;
  relatedTools: string[];
  evidenceUrls: string[];
};

export type ToolkitBrowserLab = {
  id: string;
  title: string;
  focus: string;
  riskLevel: string;
  inspectionTargets: string[];
  playwrightChecks: string[];
  evidenceOutputs: string[];
  trainingTask: string;
  acceptanceCriteria: string[];
};

export type ToolkitAuthorizationChecklist = {
  id: string;
  title: string;
  riskLevel: string;
  requiredChecks: string[];
  blockedConditions: string[];
  evidenceRequired: string[];
  approvalRule: string;
};

export type ToolkitPreflightHttpResource = {
  url: string;
  statusCode: number | null;
  contentType: string | null;
  contentLength: number | null;
  available: boolean;
  summary: string;
};

export type ToolkitPreflightRedirect = {
  url: string;
  statusCode: number;
  location: string | null;
};

export type ToolkitPreflightDom = {
  title: string | null;
  description: string | null;
  canonicalUrl: string | null;
  metaRobots: string | null;
  headings: string[];
  linkCount: number;
  scriptCount: number;
  stylesheetCount: number;
  imageCount: number;
  formCount: number;
  textSample: string;
};

export type ToolkitPreflightNetwork = {
  requestMethod: string;
  finalStatusCode: number;
  finalContentType: string | null;
  redirectCount: number;
  sameOriginLinks: number;
  externalLinks: number;
  scriptCount: number;
  stylesheetCount: number;
  imageCount: number;
  formCount: number;
};

export type ToolkitPreflightAuthorizationGate = {
  allowedToContinue: boolean;
  riskLevel: string;
  blockedReasons: string[];
  requiredNextActions: string[];
};

export type ToolkitPreflightReport = {
  requestedUrl: string;
  finalUrl: string;
  checkedAt: string;
  authorizationConfirmed: boolean;
  headers: Record<string, string>;
  redirects: ToolkitPreflightRedirect[];
  robots: ToolkitPreflightHttpResource;
  sitemap: ToolkitPreflightHttpResource;
  securityTxt: ToolkitPreflightHttpResource;
  dom: ToolkitPreflightDom;
  network: ToolkitPreflightNetwork;
  authorizationGate: ToolkitPreflightAuthorizationGate;
  recommendations: string[];
};

export type ToolkitOverview = {
  dataset: string;
  generatedAt: string | null;
  metrics: ToolkitMetrics;
  learningPaths: ToolkitLearningPath[];
  lecturePlaybooks: ToolkitLecturePlaybook[];
  imageAnchorDiagnostics: ToolkitImageAnchorDiagnostic[];
  browserLabs: ToolkitBrowserLab[];
  authorizationChecklists: ToolkitAuthorizationChecklist[];
  tools: ToolkitTool[];
  methods: ToolkitMethod[];
  intelligenceItems: ToolkitIntelligence[];
};
