import { apiFetch } from "./client";

export type TikTokToolSpec = {
  tool_id: string;
  label: string;
  description: string;
  inputs: string[];
};

export type TikTokToolRun = {
  endpoint_type: string;
  run_id?: string;
  status?: string;
  records_count?: number;
  error?: string | null;
  primary?: TikTokToolRun;
  superseded_by?: string;
  [key: string]: unknown;
};

export type TikTokToolResult = {
  tool_id: string;
  status: "success" | "partial_success" | "empty" | "failed" | string;
  records: Record<string, unknown>[];
  records_count: number;
  runs: TikTokToolRun[];
  errors: string[];
  metadata: Record<string, unknown>;
};

export async function fetchTikTokTools(): Promise<TikTokToolSpec[]> {
  return apiFetch<TikTokToolSpec[]>("/api/tiktok/tools");
}

export async function runTikTokTool(
  toolId: string,
  projectId: string,
  params: Record<string, unknown>
): Promise<TikTokToolResult> {
  return apiFetch<TikTokToolResult>(`/api/tiktok/tools/${toolId}`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId, params }),
  });
}
