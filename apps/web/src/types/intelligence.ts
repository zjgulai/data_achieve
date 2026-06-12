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
  screenshotUrl: string | null;
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
