import { apiFetch } from "@/lib/api/client";
import type {
  ToolkitIntelligence,
  ToolkitLecturePlaybook,
  ToolkitLearningPath,
  ToolkitMethod,
  ToolkitMetrics,
  ToolkitOverview,
  ToolkitTool,
} from "@/types/toolkit";

type ToolkitOverviewResponse = {
  dataset: string;
  generated_at: string | null;
  metrics: ToolkitMetricsResponse;
  learning_paths: ToolkitLearningPathResponse[];
  lecture_playbooks: ToolkitLecturePlaybookResponse[];
  tools: ToolkitToolResponse[];
  methods: ToolkitMethodResponse[];
  intelligence_items: ToolkitIntelligenceResponse[];
};

type ToolkitMetricsResponse = {
  source_count: number;
  tool_count: number;
  method_count: number;
  intelligence_count: number;
  evidence_count: number;
  last_collected_at: string | null;
};

type ToolkitToolResponse = {
  id: string;
  name: string;
  category: string;
  risk_level: string;
  collector_type: string;
  source_title: string;
  source_url: string | null;
  description: string | null;
  language: string | null;
  license: string | null;
  stars: number | null;
  forks: number | null;
  open_issues: number | null;
  updated_at: string | null;
  collected_at: string;
};

type ToolkitMethodResponse = {
  id: string;
  title: string;
  category: string;
  risk_level: string;
  collector_type: string;
  source_url: string | null;
  platform: string | null;
  recommended_collector: string | null;
  data_types: string[];
  boundary: string | null;
  training_takeaway: string | null;
  collected_at: string;
};

type ToolkitIntelligenceResponse = {
  id: string;
  title: string;
  summary: string;
  domain: string;
  intelligence_type: string;
  final_score: number;
  evidence_count: number;
  updated_at: string;
};

type ToolkitLearningPathResponse = {
  id: string;
  title: string;
  stage: string;
  focus: string;
  risk_level: string;
  tool_count: number;
  method_count: number;
  intelligence_count: number;
  evidence_count: number;
  tools: string[];
  methods: string[];
  acceptance_criteria: string[];
  source_urls: string[];
};

type ToolkitLecturePlaybookResponse = {
  id: string;
  intelligence_id: string;
  title: string;
  audience: string;
  level: string;
  duration_minutes: number;
  claim: string;
  teaching_sequence: string[];
  hands_on_steps: string[];
  verification_steps: string[];
  risk_boundaries: string[];
  classroom_exercise: string;
  evidence_urls: string[];
  evidence_count: number;
  final_score: number;
};

export async function getToolkitOverview(): Promise<ToolkitOverview> {
  const response = await apiFetch<ToolkitOverviewResponse>("/api/toolkit");
  return {
    dataset: response.dataset,
    generatedAt: response.generated_at,
    metrics: mapMetrics(response.metrics),
    learningPaths: response.learning_paths.map(mapLearningPath),
    lecturePlaybooks: response.lecture_playbooks.map(mapLecturePlaybook),
    tools: response.tools.map(mapTool),
    methods: response.methods.map(mapMethod),
    intelligenceItems: response.intelligence_items.map(mapIntelligence),
  };
}

function mapMetrics(response: ToolkitMetricsResponse): ToolkitMetrics {
  return {
    sourceCount: response.source_count,
    toolCount: response.tool_count,
    methodCount: response.method_count,
    intelligenceCount: response.intelligence_count,
    evidenceCount: response.evidence_count,
    lastCollectedAt: response.last_collected_at,
  };
}

function mapTool(response: ToolkitToolResponse): ToolkitTool {
  return {
    id: response.id,
    name: response.name,
    category: response.category,
    riskLevel: response.risk_level,
    collectorType: response.collector_type,
    sourceTitle: response.source_title,
    sourceUrl: response.source_url,
    description: response.description,
    language: response.language,
    license: response.license,
    stars: response.stars,
    forks: response.forks,
    openIssues: response.open_issues,
    updatedAt: response.updated_at,
    collectedAt: response.collected_at,
  };
}

function mapMethod(response: ToolkitMethodResponse): ToolkitMethod {
  return {
    id: response.id,
    title: response.title,
    category: response.category,
    riskLevel: response.risk_level,
    collectorType: response.collector_type,
    sourceUrl: response.source_url,
    platform: response.platform,
    recommendedCollector: response.recommended_collector,
    dataTypes: response.data_types,
    boundary: response.boundary,
    trainingTakeaway: response.training_takeaway,
    collectedAt: response.collected_at,
  };
}

function mapIntelligence(response: ToolkitIntelligenceResponse): ToolkitIntelligence {
  return {
    id: response.id,
    title: response.title,
    summary: response.summary,
    domain: response.domain,
    intelligenceType: response.intelligence_type,
    finalScore: response.final_score,
    evidenceCount: response.evidence_count,
    updatedAt: response.updated_at,
  };
}

function mapLearningPath(response: ToolkitLearningPathResponse): ToolkitLearningPath {
  return {
    id: response.id,
    title: response.title,
    stage: response.stage,
    focus: response.focus,
    riskLevel: response.risk_level,
    toolCount: response.tool_count,
    methodCount: response.method_count,
    intelligenceCount: response.intelligence_count,
    evidenceCount: response.evidence_count,
    tools: response.tools,
    methods: response.methods,
    acceptanceCriteria: response.acceptance_criteria,
    sourceUrls: response.source_urls,
  };
}

function mapLecturePlaybook(
  response: ToolkitLecturePlaybookResponse,
): ToolkitLecturePlaybook {
  return {
    id: response.id,
    intelligenceId: response.intelligence_id,
    title: response.title,
    audience: response.audience,
    level: response.level,
    durationMinutes: response.duration_minutes,
    claim: response.claim,
    teachingSequence: response.teaching_sequence,
    handsOnSteps: response.hands_on_steps,
    verificationSteps: response.verification_steps,
    riskBoundaries: response.risk_boundaries,
    classroomExercise: response.classroom_exercise,
    evidenceUrls: response.evidence_urls,
    evidenceCount: response.evidence_count,
    finalScore: response.final_score,
  };
}
