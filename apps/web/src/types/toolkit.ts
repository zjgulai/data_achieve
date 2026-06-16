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

export type ToolkitOverview = {
  dataset: string;
  generatedAt: string | null;
  metrics: ToolkitMetrics;
  learningPaths: ToolkitLearningPath[];
  lecturePlaybooks: ToolkitLecturePlaybook[];
  tools: ToolkitTool[];
  methods: ToolkitMethod[];
  intelligenceItems: ToolkitIntelligence[];
};
