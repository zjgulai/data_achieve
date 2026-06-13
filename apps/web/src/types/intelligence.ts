export type IntelligenceStatus = "new" | "reviewed" | "following" | "dismissed" | "converted";

export type IntelligenceType = "opportunity" | "risk" | "trend" | "competitor" | "anomaly";

export type FeedbackType = "useful" | "not_useful" | "false_positive";

export type IntelligenceItem = {
  id: string;
  workspaceId: string;
  projectId: string;
  title: string;
  summary: string;
  intelligenceType: IntelligenceType | string;
  status: IntelligenceStatus | string;
  impactScore: number;
  confidenceScore: number;
  noveltyScore: number;
  urgencyScore: number;
  finalScore: number;
  generatedBy: string;
  domain: string;
  evidenceCount: number;
  createdAt: string;
  updatedAt: string;
};

export type EvidenceSignalContext = {
  id: string;
  signalType: string;
  severity: string;
  previousSnapshotId: string;
  currentSnapshotId: string;
  currentValue: number | null;
  previousValue: number | null;
  delta: number | null;
  deltaRatio: number | null;
  confidence: number;
  metadata: Record<string, unknown>;
  detectedAt: string;
};

export type EvidenceEntityContext = {
  id: string;
  entityType: string;
  externalId: string;
  canonicalUrl: string | null;
  name: string;
  domain: string;
  latestSnapshotId: string | null;
};

export type EvidenceRawRecordContext = {
  id: string;
  sourceId: string;
  taskRunId: string;
  recordType: string;
  sourceUrl: string | null;
  contentHash: string;
  screenshotUrl: string | null;
  contentPreview: Record<string, unknown> | unknown[] | string;
  collectedAt: string;
  createdAt: string;
};

export type EvidenceTaskRunContext = {
  id: string;
  taskId: string;
  status: string;
  startedAt: string | null;
  finishedAt: string | null;
  recordsCount: number;
  entitiesCount: number;
  errorMessage: string | null;
};

export type EvidenceSourceContext = {
  id: string;
  name: string;
  type: string;
  url: string | null;
  enabled: boolean;
};

export type Evidence = {
  id: string;
  intelligenceId: string;
  signalId: string | null;
  entityId: string | null;
  rawRecordId: string | null;
  evidenceType: "signal" | "snapshot" | "raw_record" | "url" | string;
  title: string;
  url: string | null;
  excerpt: string | null;
  highlightedText: string | null;
  referenceMetadata: Record<string, unknown> | null;
  screenshotUrl: string | null;
  signal: EvidenceSignalContext | null;
  entity: EvidenceEntityContext | null;
  rawRecord: EvidenceRawRecordContext | null;
  taskRun: EvidenceTaskRunContext | null;
  source: EvidenceSourceContext | null;
  createdAt: string;
};

export type IntelligenceFeedback = {
  id: string;
  intelligenceId: string;
  userId: string;
  feedbackType: FeedbackType | string;
  comment: string | null;
  createdAt: string;
};

export type IntelligenceFilters = {
  projectId?: string;
  type?: string;
  status?: string;
  domain?: string;
  sort?: string;
};
