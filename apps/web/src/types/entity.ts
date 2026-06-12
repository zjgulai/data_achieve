export type Entity = {
  id: string;
  workspaceId: string;
  projectId: string;
  entityType: string;
  externalId: string;
  canonicalUrl: string | null;
  name: string;
  domain: string;
  latestSnapshotId: string | null;
  firstSeenAt: string;
  lastSeenAt: string;
};

export type EntitySnapshot = {
  id: string;
  entityId: string;
  rawRecordId: string;
  snapshotData: Record<string, unknown>;
  metrics: Record<string, unknown>;
  capturedAt: string;
  createdAt: string;
};
