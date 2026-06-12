import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockEvidences, getMockIntelligence } from "@/lib/api/mock";
import type {
  Evidence,
  FeedbackType,
  IntelligenceFeedback,
  IntelligenceFilters,
  IntelligenceItem,
  IntelligenceStatus,
} from "@/types/intelligence";

type IntelligenceResponse = {
  id: string;
  workspace_id: string;
  project_id: string;
  title: string;
  summary: string;
  intelligence_type: string;
  status: string;
  impact_score: number;
  confidence_score: number;
  novelty_score: number;
  urgency_score: number;
  final_score: number;
  generated_by: string;
  domain: string;
  evidence_count: number;
  created_at: string;
  updated_at: string;
};

type EvidenceResponse = {
  id: string;
  intelligence_id: string;
  signal_id: string | null;
  entity_id: string | null;
  raw_record_id: string | null;
  evidence_type: string;
  title: string;
  url: string | null;
  excerpt: string | null;
  highlighted_text: string | null;
  screenshot_url: string | null;
  created_at: string;
};

type FeedbackResponse = {
  id: string;
  intelligence_id: string;
  user_id: string;
  feedback_type: string;
  comment: string | null;
  created_at: string;
};

export async function listIntelligence(
  filters: IntelligenceFilters = {},
): Promise<IntelligenceItem[]> {
  if (mockApiEnabled) {
    return getMockIntelligence().filter((item) => {
      return (
        (!filters.type || item.intelligenceType === filters.type) &&
        (!filters.status || item.status === filters.status) &&
        (!filters.domain || item.domain === filters.domain) &&
        (!filters.projectId || item.projectId === filters.projectId)
      );
    });
  }
  const query = new URLSearchParams();
  if (filters.projectId) {
    query.set("project_id", filters.projectId);
  }
  if (filters.type) {
    query.set("type", filters.type);
  }
  if (filters.status) {
    query.set("status", filters.status);
  }
  if (filters.domain) {
    query.set("domain", filters.domain);
  }
  if (filters.sort) {
    query.set("sort", filters.sort);
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  const response = await apiFetch<IntelligenceResponse[]>(`/api/intelligence${suffix}`);
  return response.map(mapIntelligence);
}

export async function listEvidences(intelligenceId: string): Promise<Evidence[]> {
  if (mockApiEnabled) {
    return getMockEvidences(intelligenceId);
  }
  const response = await apiFetch<EvidenceResponse[]>(
    `/api/intelligence/${intelligenceId}/evidences`,
  );
  return response.map(mapEvidence);
}

export async function getIntelligence(intelligenceId: string): Promise<IntelligenceItem> {
  if (mockApiEnabled) {
    const item = getMockIntelligence().find((entry) => entry.id === intelligenceId);
    if (!item) {
      throw new Error("Intelligence item not found");
    }
    return item;
  }
  const response = await apiFetch<IntelligenceResponse>(`/api/intelligence/${intelligenceId}`);
  return mapIntelligence(response);
}

export async function updateIntelligenceStatus(
  intelligenceId: string,
  status: IntelligenceStatus,
): Promise<IntelligenceItem> {
  if (mockApiEnabled) {
    const item = getMockIntelligence().find((entry) => entry.id === intelligenceId);
    if (!item) {
      throw new Error("Intelligence item not found");
    }
    return { ...item, status };
  }
  const response = await apiFetch<IntelligenceResponse>(
    `/api/intelligence/${intelligenceId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    },
  );
  return mapIntelligence(response);
}

export async function submitFeedback(
  intelligenceId: string,
  feedbackType: FeedbackType,
  comment?: string,
): Promise<IntelligenceFeedback> {
  if (mockApiEnabled) {
    return {
      id: `feedback_${Date.now()}`,
      intelligenceId,
      userId: "user_mock",
      feedbackType,
      comment: comment ?? null,
      createdAt: new Date().toISOString(),
    };
  }
  const response = await apiFetch<FeedbackResponse>(
    `/api/intelligence/${intelligenceId}/feedback`,
    {
      method: "POST",
      body: JSON.stringify({
        feedback_type: feedbackType,
        comment: comment ?? null,
      }),
    },
  );
  return mapFeedback(response);
}

function mapIntelligence(response: IntelligenceResponse): IntelligenceItem {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    title: response.title,
    summary: response.summary,
    intelligenceType: response.intelligence_type,
    status: response.status,
    impactScore: response.impact_score,
    confidenceScore: response.confidence_score,
    noveltyScore: response.novelty_score,
    urgencyScore: response.urgency_score,
    finalScore: response.final_score,
    generatedBy: response.generated_by,
    domain: response.domain,
    evidenceCount: response.evidence_count,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
  };
}

function mapEvidence(response: EvidenceResponse): Evidence {
  return {
    id: response.id,
    intelligenceId: response.intelligence_id,
    signalId: response.signal_id,
    entityId: response.entity_id,
    rawRecordId: response.raw_record_id,
    evidenceType: response.evidence_type,
    title: response.title,
    url: response.url,
    excerpt: response.excerpt,
    highlightedText: response.highlighted_text,
    screenshotUrl: response.screenshot_url,
    createdAt: response.created_at,
  };
}

function mapFeedback(response: FeedbackResponse): IntelligenceFeedback {
  return {
    id: response.id,
    intelligenceId: response.intelligence_id,
    userId: response.user_id,
    feedbackType: response.feedback_type,
    comment: response.comment,
    createdAt: response.created_at,
  };
}
