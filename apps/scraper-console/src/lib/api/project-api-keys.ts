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

/** 原地更新密钥的白名单与日额度。至少要给一项，否则后端 400。 */
export function patchProjectApiKey(
  projectId: string,
  keyId: string,
  payload: { tool_allowlist?: string[]; daily_collect_quota?: number }
): Promise<ProjectApiKey> {
  return apiFetch<ProjectApiKey>(
    `/api/projects/${projectId}/api-keys/${keyId}`,
    { method: "PATCH", body: JSON.stringify(payload) }
  );
}