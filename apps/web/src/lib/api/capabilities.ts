import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  buildMockCapabilityAssertions,
  buildMockCapabilityImplementationDetailDto,
  buildMockCapabilityImplementations,
  buildMockCapabilityMatrixDto,
} from "@/lib/capability-mock";
import type {
  CapabilityAssertion,
  CapabilityAssertionDto,
  CapabilityAssertionFilters,
  CapabilityImplementation,
  CapabilityImplementationDetail,
  CapabilityImplementationDetailDto,
  CapabilityImplementationDto,
  CapabilityImplementationFilters,
  CapabilityMatrix,
  CapabilityMatrixCell,
  CapabilityMatrixCellDto,
  CapabilityMatrixResponseDto,
} from "@/types/capability";

const CAPABILITY_MATRIX_PATH = "/api/capabilities/matrix";
const CAPABILITY_ASSERTIONS_PATH = "/api/capabilities/assertions";
const CAPABILITY_IMPLEMENTATIONS_PATH = "/api/capabilities/implementations";

export function mapCapabilityMatrixCell(
  cell: CapabilityMatrixCellDto,
): CapabilityMatrixCell {
  return {
    platform: cell.platform,
    accessChannel: cell.access_channel,
    summaryStatus: cell.summary_status,
    statusCounts: cell.status_counts,
    implementationIds: cell.implementation_ids,
    assertionIds: cell.assertion_ids,
    resourceTypes: cell.resource_types,
    operations: cell.operations,
    constraintCodes: cell.constraint_codes,
    evidenceCount: cell.evidence_count,
    lastVerifiedAt: cell.last_verified_at,
  };
}

export function mapCapabilityMatrixResponse(
  response: CapabilityMatrixResponseDto,
): CapabilityMatrix {
  return {
    schemaVersion: response.schema_version,
    generatedAt: response.generated_at,
    evidenceLevel: response.evidence_level,
    providerCall: response.provider_call,
    productionWriteAllowed: response.production_write_allowed,
    platforms: response.platforms,
    accessChannels: response.access_channels,
    cells: response.cells.map(mapCapabilityMatrixCell),
    summary: {
      cellCount: response.summary.cell_count,
      populatedCellCount: response.summary.populated_cell_count,
      unknownCellCount: response.summary.unknown_cell_count,
      implementationCount: response.summary.implementation_count,
      assertionCount: response.summary.assertion_count,
      evidenceCount: response.summary.evidence_count,
    },
  };
}

export function mapCapabilityImplementation(
  implementation: CapabilityImplementationDto,
): CapabilityImplementation {
  return {
    implementationId: implementation.implementation_id,
    providerId: implementation.provider_id,
    platform: implementation.platform,
    accessChannel: implementation.access_channel,
    deliveryForm: implementation.delivery_form,
    deploymentMode: implementation.deployment_mode,
    dataDomains: implementation.data_domains,
    resourceGroups: implementation.resource_groups,
    officialDocs: implementation.official_docs,
    sdkSelection: implementation.sdk_selection,
    authMode: implementation.auth_mode,
    quotaHint: implementation.quota_hint,
    costHint: implementation.cost_hint,
    policyFlags: implementation.policy_flags,
    blockedActions: implementation.blocked_actions,
    stability: implementation.stability,
    apiVersion: implementation.api_version,
    requiredCredentials: implementation.required_credentials,
    supportedEndpoints: implementation.supported_endpoints,
    lifecycleStatus: implementation.lifecycle_status,
  };
}

export function mapCapabilityImplementationDetail(
  detail: CapabilityImplementationDetailDto,
): CapabilityImplementationDetail {
  return {
    schemaVersion: detail.schema_version,
    implementation: mapCapabilityImplementation(detail.implementation),
    assertions: detail.assertions,
    evidence: detail.evidence,
  };
}

export function buildCapabilityQuery(
  filters: CapabilityAssertionFilters | CapabilityImplementationFilters,
): URLSearchParams {
  const query = new URLSearchParams();
  if (filters.platform) {
    query.set("platform", filters.platform);
  }
  if (filters.accessChannel) {
    query.set("access_channel", filters.accessChannel);
  }
  if ("resourceType" in filters && filters.resourceType) {
    query.set("resource_type", filters.resourceType);
  }
  if ("operation" in filters && filters.operation) {
    query.set("operation", filters.operation);
  }
  if ("supportStatus" in filters && filters.supportStatus) {
    query.set("support_status", filters.supportStatus);
  }
  return query;
}

function appendCapabilityQuery(path: string, query: URLSearchParams): string {
  const encoded = query.toString();
  return encoded.length > 0 ? `${path}?${encoded}` : path;
}

function filterMockCapabilityImplementations(
  implementations: CapabilityImplementation[],
  filters: CapabilityImplementationFilters,
): CapabilityImplementation[] {
  return implementations.filter(
    (implementation) =>
      (!filters.platform || implementation.platform === filters.platform) &&
      (!filters.accessChannel ||
        implementation.accessChannel === filters.accessChannel),
  );
}

function filterMockCapabilityAssertions(
  assertions: CapabilityAssertion[],
  implementations: CapabilityImplementation[],
  filters: CapabilityAssertionFilters,
): CapabilityAssertion[] {
  const implementationById = new Map(
    implementations.map((implementation) => [
      implementation.implementationId,
      implementation,
    ]),
  );

  return assertions.filter((assertion) => {
    const implementation = implementationById.get(assertion.implementation_id);
    return (
      Boolean(implementation) &&
      (!filters.platform || implementation?.platform === filters.platform) &&
      (!filters.accessChannel ||
        implementation?.accessChannel === filters.accessChannel) &&
      (!filters.resourceType || assertion.resource_type === filters.resourceType) &&
      (!filters.operation || assertion.operation === filters.operation) &&
      (!filters.supportStatus ||
        assertion.support_status === filters.supportStatus)
    );
  });
}

export async function getCapabilityMatrix(): Promise<CapabilityMatrix> {
  if (mockApiEnabled) {
    return mapCapabilityMatrixResponse(buildMockCapabilityMatrixDto());
  }

  const response = await apiFetch<CapabilityMatrixResponseDto>(
    CAPABILITY_MATRIX_PATH,
  );
  return mapCapabilityMatrixResponse(response);
}

export async function listCapabilityImplementations(
  filters: CapabilityImplementationFilters = {},
): Promise<CapabilityImplementation[]> {
  if (mockApiEnabled) {
    return filterMockCapabilityImplementations(
      buildMockCapabilityImplementations(),
      filters,
    );
  }

  const query = buildCapabilityQuery(filters);
  const response = await apiFetch<CapabilityImplementationDto[]>(
    appendCapabilityQuery(CAPABILITY_IMPLEMENTATIONS_PATH, query),
  );
  return response.map(mapCapabilityImplementation);
}

export async function listCapabilityAssertions(
  filters: CapabilityAssertionFilters = {},
): Promise<CapabilityAssertion[]> {
  if (mockApiEnabled) {
    const implementations = buildMockCapabilityImplementations();
    return filterMockCapabilityAssertions(
      buildMockCapabilityAssertions(),
      implementations,
      filters,
    );
  }

  const query = buildCapabilityQuery(filters);
  return apiFetch<CapabilityAssertionDto[]>(
    appendCapabilityQuery(CAPABILITY_ASSERTIONS_PATH, query),
  );
}

export async function getCapabilityImplementationDetail(
  implementationId: string,
): Promise<CapabilityImplementationDetail> {
  if (mockApiEnabled) {
    return mapCapabilityImplementationDetail(
      buildMockCapabilityImplementationDetailDto(implementationId),
    );
  }

  const response = await apiFetch<CapabilityImplementationDetailDto>(
    `${CAPABILITY_IMPLEMENTATIONS_PATH}/${encodeURIComponent(implementationId)}`,
  );
  return mapCapabilityImplementationDetail(response);
}
