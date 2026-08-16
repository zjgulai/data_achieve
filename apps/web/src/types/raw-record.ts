export type RawRecord = {
  id: string;
  workspaceId: string;
  projectId: string;
  sourceId: string | null;
  taskRunId: string | null;
  workflowRunId: string | null;
  workflowStepRunId: string | null;
  workflowLineageContractVersion: string | null;
  recordType: string;
  sourceUrl: string | null;
  content: Record<string, unknown> | unknown[];
  contentHash: string;
  screenshotUrl: string | null;
  collectedAt: string;
  createdAt: string;
};
