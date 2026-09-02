import { apiFetch } from "./client";

export type EndpointTestResult = {
  endpoint_type: string;
  last_run_id: string | null;
  last_run_status: string | null;
  last_run_at: string | null;
  last_records_count: number | null;
  last_error_message: string | null;
};

export type CollectorDocsEndpoint = {
  endpoint_type: string;
  label: string;
  platform: string;
  description: string;
  status: "verified" | "pending" | "disabled";
  required_params: string[];
  optional_params: string[];
  cost_hint: string | null;
  provider: string;
  content_type: string;
  method: string;
  param_fields: Record<string, string>;
  test_result: EndpointTestResult | null;
};

export type CollectorDocsEntry = {
  collector_type: string;
  label: string;
  platform: string;
  endpoints: CollectorDocsEndpoint[];
};

export type CollectorDocsResponse = {
  groups: CollectorDocsEntry[];
  total_endpoints: number;
  tested_endpoints: number;
  success_endpoints: number;
};

export async function fetchCollectorDocs(): Promise<CollectorDocsResponse> {
  return apiFetch<CollectorDocsResponse>("/api/collectors/docs");
}
