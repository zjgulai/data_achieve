import { apiFetch } from "./client";

export type CollectorEndpoint = {
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
