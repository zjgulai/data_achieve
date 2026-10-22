import { apiFetch } from "./client";

/** 项目 API 密钥行。永不包含明文。 */
export type ProjectApiKey = Readonly<{
  id: string;
  project_id: string;
  workspace_id: string;
  label: string;
  key_prefix: string;
  tool_allowlist: string[];
  daily_collect_quota: number;
  quota_date: string | null;
  quota_used: number;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}>;

/** 签发响应：明文只出现这一次。 */
export type IssuedProjectApiKey = ProjectApiKey & Readonly<{ plaintext: string }>;

export function fetchProjectApiKeys(projectId: string): Promise<ProjectApiKey[]> {
  return apiFetch<ProjectApiKey[]>(`/api/projects/${projectId}/api-keys`);
}

export function issueProjectApiKey(
  projectId: string,
  payload: {
    label: string;
    tool_allowlist: string[];
    daily_collect_quota: number;
  }
): Promise<IssuedProjectApiKey> {
  return apiFetch<IssuedProjectApiKey>(`/api/projects/${projectId}/api-keys`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function revokeProjectApiKey(
  projectId: string,
  keyId: string
): Promise<void> {
  return apiFetch<void>(`/api/projects/${projectId}/api-keys/${keyId}`, {
    method: "DELETE",
  });
}

/** 可授权的 MCP 工具名。与 mcp_runtime/server.py 的工具一致。 */
export const MCP_TOOL_OPTIONS = [
  "web_search",
  "web_fetch",
  "answer",
  "deep_research",
  "deep_research_start",
  "deep_research_check",
  "workspace_answer",
  "create_monitor",
  "list_monitors",
  "enrich_list",
  "enrichment_check",
  "collect",
  "get_run",
  "list_records",
  "stop",
  "balance",
] as const;