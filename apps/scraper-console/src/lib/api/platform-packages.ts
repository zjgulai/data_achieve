import { apiFetch } from "./client";

export type PackageEndpoint = Readonly<{
  capability_id: string;
  endpoint_type: string;
  label: string;
  platform: string;
  description: string;
  status: "verified" | "pending" | "disabled";
  required_params: readonly string[];
  optional_params: readonly string[];
  cost_hint: string | null;
  provider: string;
  provider_group: string;
  provider_label: string;
  content_type: string;
  method: string;
  param_fields: Readonly<Record<string, string>>;
}>;

export type PlatformPackage = Readonly<{
  platform_id: string;
  display_name: string;
  description: string;
  endpoint_count: number;
  verified_count: number;
  disabled_count: number;
  provider_groups: readonly string[];
  methods: readonly string[];
  content_types: readonly string[];
  endpoints: readonly PackageEndpoint[];
  skill_path: string;
  playbook_path: string;
  detail_path: string;
}>;

export type PlatformPackageCatalog = Readonly<{
  schema_version: string;
  catalog_digest: string;
  source_entry_count: number;
  unique_endpoint_count: number;
  capability_count: number;
  platform_count: number;
  packages: readonly PlatformPackage[];
}>;

export type PlatformPlaybook = Readonly<{
  platform_id: string;
  markdown: string;
}>;

export function fetchPlatformPackages(): Promise<PlatformPackageCatalog> {
  return apiFetch<PlatformPackageCatalog>("/api/platform-packages");
}

export function fetchPlatformPackage(platformId: string): Promise<PlatformPackage> {
  return apiFetch<PlatformPackage>(
    `/api/platform-packages/${encodeURIComponent(platformId)}`,
  );
}

export function fetchPlatformPlaybook(platformId: string): Promise<PlatformPlaybook> {
  return apiFetch<PlatformPlaybook>(
    `/api/platform-packages/${encodeURIComponent(platformId)}/playbook`,
  );
}
