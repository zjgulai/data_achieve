import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockProjects, getMockSignalSnapshotCompare, getMockSignals } from "@/lib/api/mock";
import type { Signal, SignalSnapshotCompare } from "@/types/signal";

type SignalResponse = {
  id: string;
  workspace_id: string;
  project_id: string;
  entity_id: string;
  signal_type: string;
  previous_snapshot_id: string;
  current_snapshot_id: string;
  current_value: number | null;
  previous_value: number | null;
  delta: number | null;
  delta_ratio: number | null;
  confidence: number;
  severity: string;
  metadata: Record<string, unknown>;
  detected_at: string;
};

type SnapshotCompareItemResponse = {
  id: string;
  raw_record_id: string;
  metrics: Record<string, unknown>;
  snapshot_data: Record<string, unknown>;
  captured_at: string;
  created_at: string;
};

type SnapshotMetricDiffResponse = {
  metric: string;
  previous_value: unknown;
  current_value: unknown;
  delta: number | null;
  delta_ratio: number | null;
};

type SignalSnapshotCompareResponse = {
  signal_id: string;
  entity_id: string;
  signal_type: string;
  previous_snapshot: SnapshotCompareItemResponse;
  current_snapshot: SnapshotCompareItemResponse;
  metrics_diff: SnapshotMetricDiffResponse[];
};

export async function listSignals(filter?: { domain?: string }): Promise<Signal[]> {
  if (mockApiEnabled) {
    const signals = getMockSignals();
    const domain = filter?.domain;
    if (!domain) {
      return signals;
    }
    // mock 数据没有域字段，用项目的 domain 映射。取不到映射的信号直接排除，
    // 与后端「无项目归属的信号不属于任何域」保持同一语义。
    const domainProjects = new Set(
      getMockProjects().filter((project) => project.domain === domain).map((project) => project.id),
    );
    return signals.filter((signal) => domainProjects.has(signal.projectId));
  }
  const query = new URLSearchParams();
  if (filter?.domain) {
    query.set("domain", filter.domain);
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  const response = await apiFetch<SignalResponse[]>(`/api/signals${suffix}`);
  return response.map(mapSignal);
}

export async function listEntitySignals(entityId: string): Promise<Signal[]> {
  if (mockApiEnabled) {
    return getMockSignals().filter((signal) => signal.entityId === entityId);
  }
  const response = await apiFetch<SignalResponse[]>(`/api/entities/${entityId}/signals`);
  return response.map(mapSignal);
}

export async function getSignalSnapshotCompare(
  signalId: string,
): Promise<SignalSnapshotCompare> {
  if (mockApiEnabled) {
    return getMockSignalSnapshotCompare(signalId);
  }
  const response = await apiFetch<SignalSnapshotCompareResponse>(
    `/api/signals/${signalId}/snapshot-compare`,
  );
  return mapSnapshotCompare(response);
}

function mapSignal(response: SignalResponse): Signal {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    entityId: response.entity_id,
    signalType: response.signal_type,
    previousSnapshotId: response.previous_snapshot_id,
    currentSnapshotId: response.current_snapshot_id,
    currentValue: response.current_value,
    previousValue: response.previous_value,
    delta: response.delta,
    deltaRatio: response.delta_ratio,
    confidence: response.confidence,
    severity: response.severity,
    metadata: response.metadata,
    detectedAt: response.detected_at,
  };
}

function mapSnapshotCompare(response: SignalSnapshotCompareResponse): SignalSnapshotCompare {
  return {
    signalId: response.signal_id,
    entityId: response.entity_id,
    signalType: response.signal_type,
    previousSnapshot: mapSnapshotCompareItem(response.previous_snapshot),
    currentSnapshot: mapSnapshotCompareItem(response.current_snapshot),
    metricsDiff: response.metrics_diff.map((item) => ({
      metric: item.metric,
      previousValue: item.previous_value,
      currentValue: item.current_value,
      delta: item.delta,
      deltaRatio: item.delta_ratio,
    })),
  };
}

function mapSnapshotCompareItem(response: SnapshotCompareItemResponse) {
  return {
    id: response.id,
    rawRecordId: response.raw_record_id,
    metrics: response.metrics,
    snapshotData: response.snapshot_data,
    capturedAt: response.captured_at,
    createdAt: response.created_at,
  };
}
