import { apiFetch } from "./client";

export type CollectorEndpoint = {
  endpoint_type: string;
  label: string;
  platform: string;
  description: string;
  status: "verified" | "pending" | "disabled";
  policy_block_reason?: string | null;
  required_params: string[];
  optional_params: string[];
  /**
   * 端点级参数提示。键是参数名，值是提示文本。
   * 286 行中 22 行非空。仅 19 个唯一端点带提示。
   */
  param_fields: Record<string, string>;
  cost_hint: string | null;
  provider: string;
  content_type: string;
  method: string;
};

export type CollectorEntry = {
  collector_type: string;
  label: string;
  platform: string;
  endpoints: CollectorEndpoint[];
};

export type CollectorCatalog = {
  collectors: CollectorEntry[];
};

export async function fetchCollectorCatalog(): Promise<CollectorCatalog> {
  return apiFetch<CollectorCatalog>("/api/collectors/catalog");
}
