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

export type ToolkitOverview = {
  dataset: string;
  generatedAt: string | null;
  metrics: ToolkitMetrics;
  tools: ToolkitTool[];
  methods: ToolkitMethod[];
  intelligenceItems: ToolkitIntelligence[];
};
