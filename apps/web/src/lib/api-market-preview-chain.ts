import type { ApiMarketEndpoint } from "@/types/api-market";
import type {
  SocialDatasetPreviewInput,
  SocialExecutionDryRunInput,
  SocialProviderAdapterPlanInput,
  SocialProviderReadinessInput,
  SocialProviderSourceTemplateInput,
  SocialTaskRunApprovalTemplateInput,
} from "@/types/social-provider";

type ApiMarketPreviewChainOptions = {
  credentialReference?: string;
  fixtureLimit?: number;
  maxItems?: number;
  maxRequests?: number;
  maxRows?: number;
};

export type ApiMarketPreviewChainInputs = {
  adapterPlan: SocialProviderAdapterPlanInput;
  datasetPreview: SocialDatasetPreviewInput;
  executionDryRun: SocialExecutionDryRunInput;
  readiness: SocialProviderReadinessInput;
  sourceTemplate: SocialProviderSourceTemplateInput;
  taskRunApprovalTemplate: SocialTaskRunApprovalTemplateInput;
};

export function buildApiMarketPreviewChainInputs(
  endpoint: ApiMarketEndpoint,
  options: ApiMarketPreviewChainOptions = {},
): ApiMarketPreviewChainInputs {
  const fixtureLimit = options.fixtureLimit ?? 2;
  const maxItems = options.maxItems ?? 20;
  const maxRequests = options.maxRequests ?? 5;
  const maxRows = options.maxRows ?? 20;
  const endpoints = [endpoint.endpoint];
  const displayName = `${endpoint.platformLabel} ${endpoint.endpoint}`;
  const datasetName = `${displayName} VOC fixture dataset`;
  const sourceName = `${displayName} fixture source`;
  const taskName = `${displayName} fixture task`;
  const intendedUse = `fixture-only api-market review for ${endpoint.platform} ${endpoint.endpoint}`;

  return {
    adapterPlan: {
      endpoints,
      fixtureLimit,
      maxRequests,
      platform: endpoint.platform,
    },
    datasetPreview: {
      datasetName,
      endpoint: endpoint.endpoint,
      fixtureLimit,
      maxRows,
      platform: endpoint.platform,
    },
    executionDryRun: {
      credentialReference: options.credentialReference,
      datasetName,
      endpoint: endpoint.endpoint,
      fixtureLimit,
      intendedUse,
      maxItems,
      maxRequests,
      maxRows,
      platform: endpoint.platform,
      sourceName,
      taskName,
    },
    readiness: {
      endpoints,
      platform: endpoint.platform,
    },
    sourceTemplate: {
      endpoints,
      fixtureLimit,
      platform: endpoint.platform,
      sourceName,
    },
    taskRunApprovalTemplate: {
      credentialReference: options.credentialReference,
      datasetName,
      endpoints,
      intendedUse,
      maxItems,
      maxRequests,
      maxRows,
      platform: endpoint.platform,
      sourceName,
      taskName,
    },
  };
}
