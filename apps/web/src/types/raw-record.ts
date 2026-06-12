export type RawRecord = {
  id: string;
  workspaceId: string;
  projectId: string;
  sourceId: string;
  taskRunId: string;
  recordType: string;
  sourceUrl: string | null;
  content: Record<string, unknown> | unknown[];
  contentHash: string;
  screenshotUrl: string | null;
  collectedAt: string;
  createdAt: string;
};
