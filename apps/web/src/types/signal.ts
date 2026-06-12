export type Signal = {
  id: string;
  workspaceId: string;
  projectId: string;
  entityId: string;
  signalType: string;
  previousSnapshotId: string;
  currentSnapshotId: string;
  currentValue: number | null;
  previousValue: number | null;
  delta: number | null;
  deltaRatio: number | null;
  confidence: number;
  severity: "low" | "medium" | "high" | "critical" | string;
  metadata: Record<string, unknown>;
  detectedAt: string;
};

export type SnapshotMetricDiff = {
  metric: string;
  previousValue: unknown;
  currentValue: unknown;
  delta: number | null;
  deltaRatio: number | null;
};

export type SnapshotCompareItem = {
  id: string;
  rawRecordId: string;
  metrics: Record<string, unknown>;
  snapshotData: Record<string, unknown>;
  capturedAt: string;
  createdAt: string;
};

export type SignalSnapshotCompare = {
  signalId: string;
  entityId: string;
  signalType: string;
  previousSnapshot: SnapshotCompareItem;
  currentSnapshot: SnapshotCompareItem;
  metricsDiff: SnapshotMetricDiff[];
};
