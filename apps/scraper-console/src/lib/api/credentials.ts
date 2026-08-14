import { apiFetch } from "./client";

export type CredentialField = {
  key: string;
  label: string;
  configured: boolean;
};

export type PlatformCredential = {
  platform: string;
  provider_id: string;
  label: string;
  auth_mode: string;
  fields: CredentialField[];
  configured: boolean;
  configured_field_count: number;
  updated_at: string | null;
};

export type CredentialsSettings = {
  vault_write_enabled: boolean;
  platforms: PlatformCredential[];
};

export async function fetchCredentials(): Promise<CredentialsSettings> {
  return apiFetch<CredentialsSettings>("/api/settings/platform-credentials");
}

export async function updateCredential(
  platform: string,
  values: Record<string, string>
): Promise<PlatformCredential> {
  return apiFetch<PlatformCredential>(
    `/api/settings/platform-credentials/${platform}`,
    {
      method: "PUT",
      body: JSON.stringify({ values }),
    }
  );
}

export async function deleteCredential(platform: string): Promise<PlatformCredential> {
  return apiFetch<PlatformCredential>(
    `/api/settings/platform-credentials/${platform}`,
    { method: "DELETE" }
  );
}
