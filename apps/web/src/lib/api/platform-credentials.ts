import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getSocialProviderCatalog } from "@/lib/api/social-provider";
import { socialProviderUiConfigs } from "@/lib/social-provider-config";
import type { SocialProviderPlatform } from "@/types/social-provider";

type PlatformCredentialFieldStatusDto = {
  key: string;
  label: string;
  configured: boolean;
};

type PlatformCredentialSettingsDto = {
  platform: string;
  provider_id: string;
  label: string;
  auth_mode: string;
  fields: PlatformCredentialFieldStatusDto[];
  configured: boolean;
  configured_field_count: number;
  updated_at: string | null;
  live_execution_enabled: false;
};

type PlatformCredentialSettingsResponseDto = {
  schema_version: "platform_credential_settings.v1";
  vault_write_enabled: boolean;
  provider_call_allowed: false;
  credential_read_attempted: false;
  platforms: PlatformCredentialSettingsDto[];
};

export type PlatformCredentialFieldStatus = {
  key: string;
  label: string;
  configured: boolean;
};

export type PlatformCredentialSettings = {
  platform: SocialProviderPlatform;
  providerId: string;
  label: string;
  authMode: string;
  fields: PlatformCredentialFieldStatus[];
  configured: boolean;
  configuredFieldCount: number;
  updatedAt: string | null;
  liveExecutionEnabled: false;
};

export type PlatformCredentialSettingsResponse = {
  schemaVersion: "platform_credential_settings.v1";
  vaultWriteEnabled: boolean;
  providerCallAllowed: false;
  credentialReadAttempted: false;
  platforms: PlatformCredentialSettings[];
};

const fieldLabels: Record<string, string> = {
  access_token: "Access token",
  api_key: "API key",
  app_id: "App ID",
  app_secret: "App secret",
  bearer_token: "Bearer token",
  client_id: "Client ID",
  client_secret: "Client secret",
  oauth_token: "OAuth token",
  page_access_token: "Page access token",
  scope: "OAuth scope",
};

const mockConfiguredFields = new Map<SocialProviderPlatform, Set<string>>();

function mapPlatformSettings(
  value: PlatformCredentialSettingsDto,
): PlatformCredentialSettings {
  return {
    platform: value.platform as SocialProviderPlatform,
    providerId: value.provider_id,
    label: value.label,
    authMode: value.auth_mode,
    fields: value.fields.map((field) => ({ ...field })),
    configured: value.configured,
    configuredFieldCount: value.configured_field_count,
    updatedAt: value.updated_at,
    liveExecutionEnabled: value.live_execution_enabled,
  };
}

function mapSettingsResponse(
  value: PlatformCredentialSettingsResponseDto,
): PlatformCredentialSettingsResponse {
  return {
    schemaVersion: value.schema_version,
    vaultWriteEnabled: value.vault_write_enabled,
    providerCallAllowed: value.provider_call_allowed,
    credentialReadAttempted: value.credential_read_attempted,
    platforms: value.platforms.map(mapPlatformSettings),
  };
}

async function mockPlatformSettings(): Promise<PlatformCredentialSettingsResponse> {
  const platforms = await Promise.all(
    socialProviderUiConfigs.map(async (config) => {
      const catalog = await getSocialProviderCatalog(config.platform);
      const provider = catalog.providers[0];
      if (!provider) {
        throw new Error(
          `Platform credential catalog missing: ${config.platform}`,
        );
      }
      const configured =
        mockConfiguredFields.get(config.platform) ?? new Set<string>();
      const fields = provider.requiredCredentials.map((key) => ({
        key,
        label: fieldLabels[key] ?? key.replaceAll("_", " "),
        configured: configured.has(key),
      }));
      return {
        platform: config.platform,
        providerId: provider.providerId,
        label: config.label,
        authMode: provider.authMode,
        fields,
        configured:
          fields.length > 0 && fields.every((field) => field.configured),
        configuredFieldCount: fields.filter((field) => field.configured).length,
        updatedAt: configured.size > 0 ? "2026-07-22T10:00:00Z" : null,
        liveExecutionEnabled: false as const,
      };
    }),
  );
  platforms.sort((left, right) => left.platform.localeCompare(right.platform));
  return {
    schemaVersion: "platform_credential_settings.v1",
    vaultWriteEnabled: true,
    providerCallAllowed: false,
    credentialReadAttempted: false,
    platforms,
  };
}

export async function getPlatformCredentialSettings(): Promise<PlatformCredentialSettingsResponse> {
  if (mockApiEnabled) {
    return mockPlatformSettings();
  }
  const response = await apiFetch<PlatformCredentialSettingsResponseDto>(
    "/api/settings/platform-credentials",
  );
  return mapSettingsResponse(response);
}

export async function updatePlatformCredentials(
  platform: SocialProviderPlatform,
  values: Record<string, string>,
): Promise<PlatformCredentialSettings> {
  if (mockApiEnabled) {
    const settings = await mockPlatformSettings();
    const current = settings.platforms.find(
      (item) => item.platform === platform,
    );
    if (!current) {
      throw new Error("platform_credential_platform_not_found");
    }
    const allowed = new Set(current.fields.map((field) => field.key));
    const configured = new Set(mockConfiguredFields.get(platform));
    for (const [key, value] of Object.entries(values)) {
      if (!allowed.has(key) || value.length === 0) {
        throw new Error("platform_credential_field_invalid");
      }
      configured.add(key);
    }
    mockConfiguredFields.set(platform, configured);
    return (await mockPlatformSettings()).platforms.find(
      (item) => item.platform === platform,
    )!;
  }
  const response = await apiFetch<PlatformCredentialSettingsDto>(
    `/api/settings/platform-credentials/${platform}`,
    {
      body: JSON.stringify({ values }),
      method: "PUT",
    },
  );
  return mapPlatformSettings(response);
}

export async function removePlatformCredentials(
  platform: SocialProviderPlatform,
): Promise<PlatformCredentialSettings> {
  if (mockApiEnabled) {
    mockConfiguredFields.delete(platform);
    return (await mockPlatformSettings()).platforms.find(
      (item) => item.platform === platform,
    )!;
  }
  const response = await apiFetch<PlatformCredentialSettingsDto>(
    `/api/settings/platform-credentials/${platform}`,
    { method: "DELETE" },
  );
  return mapPlatformSettings(response);
}

export function clearMockPlatformCredentialState(): void {
  mockConfiguredFields.clear();
}
