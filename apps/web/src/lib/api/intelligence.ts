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

export type IntelligenceResponse = {
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

export type EvidenceResponse = {
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
  reference_metadata: Record<string, unknown> | null;
  screenshot_url: string | null;
  signal: EvidenceSignalResponse | null;
  entity: EvidenceEntityResponse | null;
  raw_record: EvidenceRawRecordResponse | null;
  task_run: EvidenceTaskRunResponse | null;
  source: EvidenceSourceResponse | null;
  created_at: string;
};

type EvidenceSignalResponse = {
  id: string;
  signal_type: string;
  severity: string;
  previous_snapshot_id: string;
  current_snapshot_id: string;
  current_value: number | null;
  previous_value: number | null;
  delta: number | null;
  delta_ratio: number | null;
  confidence: number;
  metadata: Record<string, unknown>;
  detected_at: string;
};

type EvidenceEntityResponse = {
  id: string;
  entity_type: string;
  external_id: string;
  canonical_url: string | null;
  name: string;
  domain: string;
  latest_snapshot_id: string | null;
};

type EvidenceRawRecordResponse = {
  id: string;
  source_id: string;
  task_run_id: string;
  record_type: string;
  source_url: string | null;
  content_hash: string;
  screenshot_url: string | null;
  content_preview: Record<string, unknown> | unknown[] | string;
  collected_at: string;
  created_at: string;
};

type EvidenceTaskRunResponse = {
  id: string;
  task_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  records_count: number;
  entities_count: number;
  error_message: string | null;
};

type EvidenceSourceResponse = {
  id: string;
  name: string;
  type: string;
  url: string | null;
  enabled: boolean;
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

export function mapIntelligence(response: IntelligenceResponse): IntelligenceItem {
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

export function mapEvidence(response: EvidenceResponse): Evidence {
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
    referenceMetadata: response.reference_metadata,
    screenshotUrl: response.screenshot_url,
    signal: response.signal
      ? {
          id: response.signal.id,
          signalType: response.signal.signal_type,
          severity: response.signal.severity,
          previousSnapshotId: response.signal.previous_snapshot_id,
          currentSnapshotId: response.signal.current_snapshot_id,
          currentValue: response.signal.current_value,
          previousValue: response.signal.previous_value,
          delta: response.signal.delta,
          deltaRatio: response.signal.delta_ratio,
          confidence: response.signal.confidence,
          metadata: response.signal.metadata,
          detectedAt: response.signal.detected_at,
        }
      : null,
    entity: response.entity
      ? {
          id: response.entity.id,
          entityType: response.entity.entity_type,
          externalId: response.entity.external_id,
          canonicalUrl: response.entity.canonical_url,
          name: response.entity.name,
          domain: response.entity.domain,
          latestSnapshotId: response.entity.latest_snapshot_id,
        }
      : null,
    rawRecord: response.raw_record
      ? {
          id: response.raw_record.id,
          sourceId: response.raw_record.source_id,
          taskRunId: response.raw_record.task_run_id,
          recordType: response.raw_record.record_type,
          sourceUrl: response.raw_record.source_url,
          contentHash: response.raw_record.content_hash,
          screenshotUrl: response.raw_record.screenshot_url,
          contentPreview: response.raw_record.content_preview,
          collectedAt: response.raw_record.collected_at,
          createdAt: response.raw_record.created_at,
        }
      : null,
    taskRun: response.task_run
      ? {
          id: response.task_run.id,
          taskId: response.task_run.task_id,
          status: response.task_run.status,
          startedAt: response.task_run.started_at,
          finishedAt: response.task_run.finished_at,
          recordsCount: response.task_run.records_count,
          entitiesCount: response.task_run.entities_count,
          errorMessage: response.task_run.error_message,
        }
      : null,
    source: response.source
      ? {
          id: response.source.id,
          name: response.source.name,
          type: response.source.type,
          url: response.source.url,
          enabled: response.source.enabled,
        }
      : null,
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
