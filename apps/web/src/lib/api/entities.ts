import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockEntities, getMockEntitySnapshots } from "@/lib/api/mock";
import type { Entity, EntitySnapshot } from "@/types/entity";

type EntityResponse = {
  id: string;
  workspace_id: string;
  project_id: string;
  entity_type: string;
  external_id: string;
  canonical_url: string | null;
  name: string;
  domain: string;
  latest_snapshot_id: string | null;
  first_seen_at: string;
  last_seen_at: string;
};

type EntitySnapshotResponse = {
  id: string;
  entity_id: string;
  raw_record_id: string;
  snapshot_data: Record<string, unknown>;
  metrics: Record<string, unknown>;
  captured_at: string;
  created_at: string;
};

export async function listEntities(): Promise<Entity[]> {
  if (mockApiEnabled) {
    return getMockEntities();
  }
  const response = await apiFetch<EntityResponse[]>("/api/entities");
  return response.map(mapEntity);
}

export async function listEntitySnapshots(entityId: string): Promise<EntitySnapshot[]> {
  if (mockApiEnabled) {
    return getMockEntitySnapshots(entityId);
  }
  const response = await apiFetch<EntitySnapshotResponse[]>(
    `/api/entities/${entityId}/snapshots`,
  );
  return response.map(mapEntitySnapshot);
}

function mapEntity(response: EntityResponse): Entity {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    entityType: response.entity_type,
    externalId: response.external_id,
    canonicalUrl: response.canonical_url,
    name: response.name,
    domain: response.domain,
    latestSnapshotId: response.latest_snapshot_id,
    firstSeenAt: response.first_seen_at,
    lastSeenAt: response.last_seen_at,
  };
}

function mapEntitySnapshot(response: EntitySnapshotResponse): EntitySnapshot {
  return {
    id: response.id,
    entityId: response.entity_id,
    rawRecordId: response.raw_record_id,
    snapshotData: response.snapshot_data,
    metrics: response.metrics,
    capturedAt: response.captured_at,
    createdAt: response.created_at,
  };
}
