import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { buildMockCapabilityDiscoveryPreviewDto } from "@/lib/capability-discovery-mock";
import type {
  CapabilityDiscoveryCandidateAssertion,
  CapabilityDiscoveryCandidateAssertionDto,
  CapabilityDiscoveryConstraint,
  CapabilityDiscoveryConstraintDto,
  CapabilityDiscoveryDiagnostic,
  CapabilityDiscoveryDiagnosticDto,
  CapabilityDiscoveryEvidence,
  CapabilityDiscoveryEvidenceDto,
  CapabilityDiscoveryFixtureId,
  CapabilityDiscoveryPreview,
  CapabilityDiscoveryPreviewRequestDto,
  CapabilityDiscoveryPreviewResponseDto,
  CapabilityDiscoveryProposedImplementation,
  CapabilityDiscoveryProposedImplementationDto,
  CapabilityDiscoverySourceSnapshot,
  CapabilityDiscoverySourceSnapshotDto,
} from "@/types/capability-discovery";

const CAPABILITY_DISCOVERY_PREVIEW_PATH =
  "/api/capabilities/discovery/preview";

export const DEFAULT_CAPABILITY_DISCOVERY_FIXTURE_IDS = [
  "tikhub-youtube-market-v1",
  "apify-reddit-market-v1",
  "youtube-data-api-doc-v1",
  "reddit-data-api-doc-v1",
] as const satisfies readonly CapabilityDiscoveryFixtureId[];

export function buildCapabilityDiscoveryPreviewRequest(
  fixtureIds: readonly CapabilityDiscoveryFixtureId[] =
    DEFAULT_CAPABILITY_DISCOVERY_FIXTURE_IDS,
): CapabilityDiscoveryPreviewRequestDto {
  return {
    schema_version: "capability_discovery_preview_request.v1",
    preview_mode: "fixture_replay",
    fixture_ids: [...fixtureIds],
  };
}

function mapConstraint(
  constraint: CapabilityDiscoveryConstraintDto,
): CapabilityDiscoveryConstraint {
  return {
    constraintType: constraint.constraint_type,
    severity: constraint.severity,
    code: constraint.code,
    details: constraint.details,
  };
}

function mapSourceSnapshot(
  source: CapabilityDiscoverySourceSnapshotDto,
): CapabilityDiscoverySourceSnapshot {
  return {
    schemaVersion: source.schema_version,
    fixtureId: source.fixture_id,
    sourceKind: source.source_kind,
    sourceName: source.source_name,
    sourceUrl: source.source_url,
    sourceVersion: source.source_version,
    observedAt: source.observed_at,
    parserId: source.parser_id,
    contentHash: source.content_hash,
  };
}

function mapProposedImplementation(
  implementation: CapabilityDiscoveryProposedImplementationDto,
): CapabilityDiscoveryProposedImplementation {
  return {
    schemaVersion: implementation.schema_version,
    proposedImplementationId: implementation.proposed_implementation_id,
    providerId: implementation.provider_id,
    platform: implementation.platform,
    accessChannel: implementation.access_channel,
    deliveryForm: implementation.delivery_form,
    deploymentMode: implementation.deployment_mode,
    sourceLabel: implementation.source_label,
    claimedAuthMode: implementation.claimed_auth_mode,
    claimedRequiredCredentials: [
      ...implementation.claimed_required_credentials,
    ],
    claimedLimitations: [...implementation.claimed_limitations],
    evidenceRefs: [...implementation.evidence_refs],
  };
}

function mapCandidateAssertion(
  candidate: CapabilityDiscoveryCandidateAssertionDto,
): CapabilityDiscoveryCandidateAssertion {
  return {
    schemaVersion: candidate.schema_version,
    candidateId: candidate.candidate_id,
    proposedImplementationId: candidate.proposed_implementation_id,
    platform: candidate.platform,
    accessChannel: candidate.access_channel,
    resourceType: candidate.resource_type,
    operation: candidate.operation,
    supportStatus: candidate.support_status,
    verificationStatus: candidate.verification_status,
    executable: candidate.executable,
    publishable: candidate.publishable,
    claimedFieldContract: candidate.claimed_field_contract,
    claimedConstraints: candidate.claimed_constraints.map(mapConstraint),
    regionScope: [...candidate.region_scope],
    purposeScope: [...candidate.purpose_scope],
    authScope: [...candidate.auth_scope],
    sourceClaimRefs: [...candidate.source_claim_refs],
    evidenceRefs: [...candidate.evidence_refs],
    parserId: candidate.parser_id,
    candidateFingerprint: candidate.candidate_fingerprint,
  };
}

function mapEvidence(
  evidence: CapabilityDiscoveryEvidenceDto,
): CapabilityDiscoveryEvidence {
  return {
    schemaVersion: evidence.schema_version,
    evidenceId: evidence.evidence_id,
    evidenceType: evidence.evidence_type,
    sourceUrl: evidence.source_url,
    sourceVersion: evidence.source_version,
    observedAt: evidence.observed_at,
    contentHash: evidence.content_hash,
    hashScope: evidence.hash_scope,
    evidenceGrade: evidence.evidence_grade,
    providerCallAttempted: evidence.provider_call_attempted,
    credentialReadAttempted: evidence.credential_read_attempted,
    liveClientCreated: evidence.live_client_created,
    productionWriteAttempted: evidence.production_write_attempted,
  };
}

function mapDiagnostic(
  diagnostic: CapabilityDiscoveryDiagnosticDto,
): CapabilityDiscoveryDiagnostic {
  return {
    schemaVersion: diagnostic.schema_version,
    fixtureId: diagnostic.fixture_id,
    severity: diagnostic.severity,
    code: diagnostic.code,
    message: diagnostic.message,
    sourceClaimRef: diagnostic.source_claim_ref,
  };
}

export function mapCapabilityDiscoveryPreview(
  response: CapabilityDiscoveryPreviewResponseDto,
): CapabilityDiscoveryPreview {
  return {
    schemaVersion: response.schema_version,
    evidenceGrade: response.evidence_grade,
    previewMode: response.preview_mode,
    previewFingerprint: response.preview_fingerprint,
    generatedFromObservedAt: response.generated_from_observed_at,
    sourceSnapshots: response.source_snapshots.map(mapSourceSnapshot),
    proposedImplementations: response.proposed_implementations.map(
      mapProposedImplementation,
    ),
    candidateAssertions: response.candidate_assertions.map(
      mapCandidateAssertion,
    ),
    evidence: response.evidence.map(mapEvidence),
    diagnostics: response.diagnostics.map(mapDiagnostic),
    summary: {
      sourceCount: response.summary.source_count,
      marketSourceCount: response.summary.market_source_count,
      officialDocSourceCount: response.summary.official_doc_source_count,
      proposedImplementationCount:
        response.summary.proposed_implementation_count,
      candidateAssertionCount: response.summary.candidate_assertion_count,
      evidenceCount: response.summary.evidence_count,
      warningCount: response.summary.warning_count,
      errorCount: response.summary.error_count,
    },
    providerCall: response.provider_call,
    providerCallAttempted: response.provider_call_attempted,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    credentialReadAttempted: response.credential_read_attempted,
    databaseWrite: response.database_write,
    databaseMigration: response.database_migration,
    workflowRunCreated: response.workflow_run_created,
    candidatePublishAllowed: response.candidate_publish_allowed,
    productionWriteAllowed: response.production_write_allowed,
  };
}

export async function previewCapabilityDiscovery(
  fixtureIds: readonly CapabilityDiscoveryFixtureId[] =
    DEFAULT_CAPABILITY_DISCOVERY_FIXTURE_IDS,
): Promise<CapabilityDiscoveryPreview> {
  if (mockApiEnabled) {
    return mapCapabilityDiscoveryPreview(
      buildMockCapabilityDiscoveryPreviewDto(),
    );
  }

  const response = await apiFetch<CapabilityDiscoveryPreviewResponseDto>(
    CAPABILITY_DISCOVERY_PREVIEW_PATH,
    {
      method: "POST",
      body: JSON.stringify(
        buildCapabilityDiscoveryPreviewRequest(fixtureIds),
      ),
    },
  );
  return mapCapabilityDiscoveryPreview(response);
}
