import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  CapabilityGovernanceMockError,
  createMockCapabilityGovernanceStore,
} from "@/lib/capability-governance-mock";
import type { CapabilityDiscoveryFixtureId } from "@/types/capability-discovery";
import type {
  CapabilityGovernanceCandidate,
  CapabilityGovernanceCandidateAssertion,
  CapabilityGovernanceCandidateAssertionDto,
  CapabilityGovernanceCandidateDetail,
  CapabilityGovernanceCandidateDetailResponseDto,
  CapabilityGovernanceCandidateDto,
  CapabilityGovernanceCandidateList,
  CapabilityGovernanceCandidateListResponseDto,
  CapabilityGovernanceDecision,
  CapabilityGovernanceDecisionDto,
  CapabilityGovernanceImportRequestDto,
  CapabilityGovernanceImportResponse,
  CapabilityGovernanceImportResponseDto,
  CapabilityGovernanceProposedImplementation,
  CapabilityGovernanceProposedImplementationDto,
  CapabilityGovernancePublicationDetail,
  CapabilityGovernancePublicationDetailResponseDto,
  CapabilityGovernancePublicationList,
  CapabilityGovernancePublicationListResponseDto,
  CapabilityGovernancePublicationOperationInput,
  CapabilityGovernancePublicationRequestDto,
  CapabilityGovernancePublicationResponse,
  CapabilityGovernancePublicationResponseDto,
  CapabilityGovernancePublicationRevision,
  CapabilityGovernancePublicationRevisionDto,
  CapabilityGovernanceReviewInput,
  CapabilityGovernanceReviewRequestDto,
  CapabilityGovernanceReviewResponse,
  CapabilityGovernanceReviewResponseDto,
  CapabilityGovernanceRollbackRequestDto,
  CapabilityGovernanceVerificationTask,
  CapabilityGovernanceVerificationTaskDetail,
  CapabilityGovernanceVerificationTaskDetailResponseDto,
  CapabilityGovernanceVerificationTaskDto,
  CapabilityGovernanceVerificationTaskList,
  CapabilityGovernanceVerificationTaskListResponseDto,
  CapabilityGovernanceVerificationTaskStatus,
} from "@/types/capability-governance";

const GOVERNANCE_PATH = "/api/capabilities/governance";
type CapabilityGovernanceMockScenario =
  | "default"
  | "forbidden"
  | "review-conflict";

const mockStores = {
  default: createMockCapabilityGovernanceStore(),
  forbidden: createMockCapabilityGovernanceStore({
    permissions: { canRead: false, canReview: false, canPublish: false },
  }),
  "review-conflict": createMockCapabilityGovernanceStore(),
} satisfies Record<
  CapabilityGovernanceMockScenario,
  ReturnType<typeof createMockCapabilityGovernanceStore>
>;

function governanceFixtureModeEnabled(): boolean {
  return process.env.NEXT_PUBLIC_CAPABILITY_GOVERNANCE_TEST_FIXTURES === "true";
}

export function resolveCapabilityGovernanceMockScenario(
  search: string,
): CapabilityGovernanceMockScenario {
  if (!governanceFixtureModeEnabled()) return "default";
  const fixture = new URLSearchParams(search).get("governance_fixture");
  return fixture === "forbidden" || fixture === "review-conflict"
    ? fixture
    : "default";
}

function currentMockScenario(): CapabilityGovernanceMockScenario {
  const search = typeof window === "undefined" ? "" : window.location.search;
  return resolveCapabilityGovernanceMockScenario(search);
}

function currentMockStore() {
  return mockStores[currentMockScenario()];
}

export function buildCapabilityGovernanceImportRequest(
  fixtureIds: readonly CapabilityDiscoveryFixtureId[],
  expectedPreviewFingerprint: string,
): CapabilityGovernanceImportRequestDto {
  return {
    schema_version: "capability_governance_import_request.v1",
    fixture_ids: [...fixtureIds],
    expected_preview_fingerprint: expectedPreviewFingerprint,
  };
}

export function buildCapabilityGovernanceReviewRequest(
  input: CapabilityGovernanceReviewInput,
): CapabilityGovernanceReviewRequestDto {
  const base = {
    schema_version: "capability_governance_review_request.v1" as const,
    expected_task_version: input.expectedTaskVersion,
    reason: input.reason.trim(),
  };
  if (input.action === "reject") {
    return {
      ...base,
      action: "reject",
      canonical_implementation: null,
      canonical_assertion: null,
    };
  }
  return {
    ...base,
    action: input.action,
    canonical_implementation: input.canonicalImplementation,
    canonical_assertion: input.canonicalAssertion,
  };
}

export function buildCapabilityGovernancePublicationRequest(input: {
  expectedParentRevisionId: string | null;
  reason: string;
  operations: CapabilityGovernancePublicationOperationInput[];
}): CapabilityGovernancePublicationRequestDto {
  return {
    schema_version: "capability_governance_publication_request.v1",
    expected_parent_revision_id: input.expectedParentRevisionId,
    reason: input.reason.trim(),
    operations: input.operations.map((operation) =>
      operation.operation === "upsert_verified_assertion"
        ? {
            operation: operation.operation,
            verification_decision_id: operation.verificationDecisionId,
          }
        : {
            operation: operation.operation,
            verification_decision_id: operation.verificationDecisionId,
            logical_assertion_key: operation.logicalAssertionKey,
          },
    ),
  };
}

export function buildCapabilityGovernanceRollbackRequest(input: {
  expectedCurrentRevisionId: string;
  targetRevisionId: string;
  reason: string;
}): CapabilityGovernanceRollbackRequestDto {
  return {
    schema_version: "capability_governance_rollback_request.v1",
    expected_current_revision_id: input.expectedCurrentRevisionId,
    target_revision_id: input.targetRevisionId,
    reason: input.reason.trim(),
  };
}

function mapProposedImplementation(
  value: CapabilityGovernanceProposedImplementationDto,
): CapabilityGovernanceProposedImplementation {
  return {
    schemaVersion: value.schema_version,
    proposedImplementationId: value.proposed_implementation_id,
    providerId: value.provider_id,
    platform: value.platform,
    accessChannel: value.access_channel,
    deliveryForm: value.delivery_form,
    deploymentMode: value.deployment_mode,
    sourceLabel: value.source_label,
    claimedAuthMode: value.claimed_auth_mode,
    claimedRequiredCredentials: [...value.claimed_required_credentials],
    claimedLimitations: [...value.claimed_limitations],
  };
}

function mapCandidateAssertion(
  value: CapabilityGovernanceCandidateAssertionDto,
): CapabilityGovernanceCandidateAssertion {
  return {
    schemaVersion: value.schema_version,
    candidateId: value.candidate_id,
    proposedImplementationId: value.proposed_implementation_id,
    platform: value.platform,
    accessChannel: value.access_channel,
    resourceType: value.resource_type,
    operation: value.operation,
    supportStatus: value.support_status,
    verificationStatus: value.verification_status,
    executable: value.executable,
    publishable: value.publishable,
    claimedFieldContract: { ...value.claimed_field_contract },
    claimedConstraints: value.claimed_constraints.map((constraint) => ({
      ...constraint,
      details: { ...constraint.details },
    })),
    regionScope: [...value.region_scope],
    purposeScope: [...value.purpose_scope],
    authScope: [...value.auth_scope],
    parserId: value.parser_id,
    candidateFingerprint: value.candidate_fingerprint,
  };
}

function mapCandidate(
  value: CapabilityGovernanceCandidateDto,
): CapabilityGovernanceCandidate {
  return {
    id: value.id,
    candidateKey: value.candidate_key,
    semanticVersion: value.semantic_version,
    candidateFingerprint: value.candidate_fingerprint,
    predecessorId: value.predecessor_id,
    proposedImplementation: mapProposedImplementation(
      value.proposed_implementation,
    ),
    candidateAssertion: mapCandidateAssertion(value.candidate_assertion),
    firstSeenBatchId: value.first_seen_batch_id,
    createdAt: value.created_at,
  };
}

function mapTask(
  value: CapabilityGovernanceVerificationTaskDto,
): CapabilityGovernanceVerificationTask {
  return {
    id: value.id,
    candidateVersionId: value.candidate_version_id,
    taskType: value.task_type,
    status: value.status,
    taskVersion: value.task_version,
    openedAt: value.opened_at,
    resolvedAt: value.resolved_at,
    decisionId: value.decision_id,
  };
}

function mapDecision(
  value: CapabilityGovernanceDecisionDto,
): CapabilityGovernanceDecision {
  return {
    id: value.id,
    verificationTaskId: value.verification_task_id,
    candidateVersionId: value.candidate_version_id,
    action: value.action,
    verificationStatus: value.verification_status,
    reviewerUserId: value.reviewer_user_id,
    reviewedAt: value.reviewed_at,
    reason: value.reason,
    canonicalBundle:
      value.canonical_bundle === null ? null : { ...value.canonical_bundle },
  };
}

function mapRevision(
  value: CapabilityGovernancePublicationRevisionDto,
): CapabilityGovernancePublicationRevision {
  return {
    id: value.id,
    revisionNumber: value.revision_number,
    parentRevisionId: value.parent_revision_id,
    restoredFromRevisionId: value.restored_from_revision_id,
    catalogSnapshotId: value.catalog_snapshot_id,
    publisherUserId: value.publisher_user_id,
    publishedAt: value.published_at,
    reason: value.reason,
    operations: value.operations.map((operation) => ({ ...operation })),
    isCurrent: value.is_current,
  };
}

export function mapCapabilityGovernanceCandidateList(
  value: CapabilityGovernanceCandidateListResponseDto,
): CapabilityGovernanceCandidateList {
  return {
    schemaVersion: value.schema_version,
    permissions: {
      canRead: value.permissions.can_read,
      canReview: value.permissions.can_review,
      canPublish: value.permissions.can_publish,
    },
    items: value.items.map(mapCandidate),
    limit: value.limit,
    offset: value.offset,
  };
}

export function mapCapabilityGovernanceCandidateDetail(
  value: CapabilityGovernanceCandidateDetailResponseDto,
): CapabilityGovernanceCandidateDetail {
  return {
    schemaVersion: value.schema_version,
    candidate: mapCandidate(value.candidate),
    evidence: value.evidence.map((item) => ({ ...item })),
    openVerificationTask:
      value.open_verification_task === null
        ? null
        : mapTask(value.open_verification_task),
    latestDecision:
      value.latest_decision === null
        ? null
        : mapDecision(value.latest_decision),
  };
}

export function mapCapabilityGovernanceVerificationTaskList(
  value: CapabilityGovernanceVerificationTaskListResponseDto,
): CapabilityGovernanceVerificationTaskList {
  return {
    schemaVersion: value.schema_version,
    items: value.items.map(mapTask),
    limit: value.limit,
    offset: value.offset,
  };
}

export function mapCapabilityGovernanceVerificationTaskDetail(
  value: CapabilityGovernanceVerificationTaskDetailResponseDto,
): CapabilityGovernanceVerificationTaskDetail {
  return {
    schemaVersion: value.schema_version,
    task: mapTask(value.task),
    candidate: mapCandidate(value.candidate),
    evidence: value.evidence.map((item) => ({ ...item })),
    decision: value.decision === null ? null : mapDecision(value.decision),
  };
}

export function mapCapabilityGovernancePublicationList(
  value: CapabilityGovernancePublicationListResponseDto,
): CapabilityGovernancePublicationList {
  return {
    schemaVersion: value.schema_version,
    items: value.items.map(mapRevision),
    currentRevisionId: value.current_revision_id,
    limit: value.limit,
    offset: value.offset,
  };
}

export function mapCapabilityGovernancePublicationDetail(
  value: CapabilityGovernancePublicationDetailResponseDto,
): CapabilityGovernancePublicationDetail {
  return {
    schemaVersion: value.schema_version,
    revision: mapRevision(value.revision),
    currentRevisionId: value.current_revision_id,
  };
}

export function mapCapabilityGovernanceImportResponse(
  value: CapabilityGovernanceImportResponseDto,
): CapabilityGovernanceImportResponse {
  return {
    schemaVersion: value.schema_version,
    requestId: value.request_id,
    batchId: value.batch_id,
    previewFingerprint: value.preview_fingerprint,
    outcome: value.outcome,
    candidates: value.candidates.map((candidate) => ({
      candidateKey: candidate.candidate_key,
      candidateVersionId: candidate.candidate_version_id,
      semanticVersion: candidate.semantic_version,
      classification: candidate.classification,
      verificationTaskId: candidate.verification_task_id,
      evidenceAddedCount: candidate.evidence_added_count,
    })),
    databaseWrite: value.database_write,
    domainChanged: value.domain_changed,
    idempotentReplay: value.idempotent_replay,
  };
}

export function mapCapabilityGovernanceReviewResponse(
  value: CapabilityGovernanceReviewResponseDto,
): CapabilityGovernanceReviewResponse {
  return {
    schemaVersion: value.schema_version,
    requestId: value.request_id,
    decisionId: value.decision_id,
    taskId: value.task_id,
    candidateVersionId: value.candidate_version_id,
    taskVersion: value.task_version,
    action: value.action,
    verificationStatus: value.verification_status,
    reviewedAt: value.reviewed_at,
    databaseWrite: value.database_write,
    domainChanged: value.domain_changed,
    idempotentReplay: value.idempotent_replay,
  };
}

export function mapCapabilityGovernancePublicationResponse(
  value: CapabilityGovernancePublicationResponseDto,
): CapabilityGovernancePublicationResponse {
  return {
    schemaVersion: value.schema_version,
    publicationKind: value.publication_kind,
    requestId: value.request_id,
    revisionId: value.revision_id,
    revisionNumber: value.revision_number,
    parentRevisionId: value.parent_revision_id,
    restoredFromRevisionId: value.restored_from_revision_id,
    catalogSnapshotId: value.catalog_snapshot_id,
    headVersion: value.head_version,
    operationCount: value.operation_count,
    publishedAt: value.published_at,
    databaseWrite: value.database_write,
    domainChanged: value.domain_changed,
    idempotentReplay: value.idempotent_replay,
  };
}

function queryPath(
  path: string,
  values: Record<string, string | number | undefined>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined) params.set(key, String(value));
  }
  const query = params.toString();
  return query.length === 0 ? path : `${path}?${query}`;
}

function mutationInit(payload: object, idempotencyKey: string): RequestInit {
  const normalized = idempotencyKey.trim();
  if (normalized.length < 12 || normalized.length > 200) {
    throw new Error("idempotency_key_invalid");
  }
  return {
    method: "POST",
    headers: { "Idempotency-Key": normalized },
    body: JSON.stringify(payload),
  };
}

export async function listCapabilityGovernanceCandidates(
  options: { limit?: number; offset?: number } = {},
): Promise<CapabilityGovernanceCandidateList> {
  const limit = options.limit ?? 50;
  const offset = options.offset ?? 0;
  if (mockApiEnabled) {
    return mapCapabilityGovernanceCandidateList(
      currentMockStore().listCandidates({ limit, offset }),
    );
  }
  const path =
    limit === 50 && offset === 0
      ? `${GOVERNANCE_PATH}/candidates`
      : queryPath(`${GOVERNANCE_PATH}/candidates`, { limit, offset });
  return mapCapabilityGovernanceCandidateList(
    await apiFetch<CapabilityGovernanceCandidateListResponseDto>(path),
  );
}

export async function getCapabilityGovernanceCandidate(
  candidateKey: string,
): Promise<CapabilityGovernanceCandidateDetail> {
  if (mockApiEnabled) {
    return mapCapabilityGovernanceCandidateDetail(
      currentMockStore().getCandidate(candidateKey),
    );
  }
  return mapCapabilityGovernanceCandidateDetail(
    await apiFetch<CapabilityGovernanceCandidateDetailResponseDto>(
      `${GOVERNANCE_PATH}/candidates/${encodeURIComponent(candidateKey)}`,
    ),
  );
}

export async function listCapabilityGovernanceVerificationTasks(
  options: {
    status?: CapabilityGovernanceVerificationTaskStatus;
    limit?: number;
    offset?: number;
  } = {},
): Promise<CapabilityGovernanceVerificationTaskList> {
  const limit = options.limit ?? 50;
  const offset = options.offset ?? 0;
  if (mockApiEnabled) {
    return mapCapabilityGovernanceVerificationTaskList(
      currentMockStore().listVerificationTasks({
        status: options.status,
        limit,
        offset,
      }),
    );
  }
  const path =
    options.status === undefined && limit === 50 && offset === 0
      ? `${GOVERNANCE_PATH}/verification-tasks`
      : queryPath(`${GOVERNANCE_PATH}/verification-tasks`, {
          status: options.status,
          limit,
          offset,
        });
  return mapCapabilityGovernanceVerificationTaskList(
    await apiFetch<CapabilityGovernanceVerificationTaskListResponseDto>(path),
  );
}

export async function getCapabilityGovernanceVerificationTask(
  taskId: string,
): Promise<CapabilityGovernanceVerificationTaskDetail> {
  if (mockApiEnabled) {
    return mapCapabilityGovernanceVerificationTaskDetail(
      currentMockStore().getVerificationTask(taskId),
    );
  }
  return mapCapabilityGovernanceVerificationTaskDetail(
    await apiFetch<CapabilityGovernanceVerificationTaskDetailResponseDto>(
      `${GOVERNANCE_PATH}/verification-tasks/${encodeURIComponent(taskId)}`,
    ),
  );
}

export async function listCapabilityGovernancePublications(
  options: { limit?: number; offset?: number } = {},
): Promise<CapabilityGovernancePublicationList> {
  const limit = options.limit ?? 50;
  const offset = options.offset ?? 0;
  if (mockApiEnabled) {
    return mapCapabilityGovernancePublicationList(
      currentMockStore().listPublications({ limit, offset }),
    );
  }
  const path =
    limit === 50 && offset === 0
      ? `${GOVERNANCE_PATH}/publications`
      : queryPath(`${GOVERNANCE_PATH}/publications`, { limit, offset });
  return mapCapabilityGovernancePublicationList(
    await apiFetch<CapabilityGovernancePublicationListResponseDto>(path),
  );
}

export async function getCapabilityGovernancePublication(
  revisionId: string,
): Promise<CapabilityGovernancePublicationDetail> {
  if (mockApiEnabled) {
    return mapCapabilityGovernancePublicationDetail(
      currentMockStore().getPublication(revisionId),
    );
  }
  return mapCapabilityGovernancePublicationDetail(
    await apiFetch<CapabilityGovernancePublicationDetailResponseDto>(
      `${GOVERNANCE_PATH}/publications/${encodeURIComponent(revisionId)}`,
    ),
  );
}

export async function importCapabilityGovernanceCandidates(
  payload: CapabilityGovernanceImportRequestDto,
  idempotencyKey: string,
): Promise<CapabilityGovernanceImportResponse> {
  const value = mockApiEnabled
    ? currentMockStore().importCandidates(payload, idempotencyKey)
    : await apiFetch<CapabilityGovernanceImportResponseDto>(
        `${GOVERNANCE_PATH}/imports`,
        mutationInit(payload, idempotencyKey),
      );
  return mapCapabilityGovernanceImportResponse(value);
}

export async function reviewCapabilityGovernanceCandidate(
  taskId: string,
  payload: CapabilityGovernanceReviewRequestDto,
  idempotencyKey: string,
): Promise<CapabilityGovernanceReviewResponse> {
  let value: CapabilityGovernanceReviewResponseDto;
  if (mockApiEnabled) {
    if (currentMockScenario() === "review-conflict") {
      throw new CapabilityGovernanceMockError(
        "verification_task_conflict",
        409,
      );
    }
    value = currentMockStore().reviewCandidate(taskId, payload, idempotencyKey);
  } else {
    value = await apiFetch<CapabilityGovernanceReviewResponseDto>(
      `${GOVERNANCE_PATH}/verification-tasks/${encodeURIComponent(taskId)}/decisions`,
      mutationInit(payload, idempotencyKey),
    );
  }
  return mapCapabilityGovernanceReviewResponse(value);
}

export async function publishCapabilityGovernanceCatalog(
  payload: CapabilityGovernancePublicationRequestDto,
  idempotencyKey: string,
): Promise<CapabilityGovernancePublicationResponse> {
  const value = mockApiEnabled
    ? currentMockStore().publishCatalog(payload, idempotencyKey)
    : await apiFetch<CapabilityGovernancePublicationResponseDto>(
        `${GOVERNANCE_PATH}/publications`,
        mutationInit(payload, idempotencyKey),
      );
  return mapCapabilityGovernancePublicationResponse(value);
}

export async function rollbackCapabilityGovernanceCatalog(
  payload: CapabilityGovernanceRollbackRequestDto,
  idempotencyKey: string,
): Promise<CapabilityGovernancePublicationResponse> {
  const value = mockApiEnabled
    ? currentMockStore().rollbackCatalog(payload, idempotencyKey)
    : await apiFetch<CapabilityGovernancePublicationResponseDto>(
        `${GOVERNANCE_PATH}/publications/rollback`,
        mutationInit(payload, idempotencyKey),
      );
  return mapCapabilityGovernancePublicationResponse(value);
}

export type CapabilityGovernanceTransport = {
  listCandidates: typeof listCapabilityGovernanceCandidates;
  getCandidate: typeof getCapabilityGovernanceCandidate;
  listVerificationTasks: typeof listCapabilityGovernanceVerificationTasks;
  getVerificationTask: typeof getCapabilityGovernanceVerificationTask;
  listPublications: typeof listCapabilityGovernancePublications;
  getPublication: typeof getCapabilityGovernancePublication;
  importCandidates: typeof importCapabilityGovernanceCandidates;
  reviewCandidate: typeof reviewCapabilityGovernanceCandidate;
  publishCatalog: typeof publishCapabilityGovernanceCatalog;
  rollbackCatalog: typeof rollbackCapabilityGovernanceCatalog;
};

export const capabilityGovernanceTransport: CapabilityGovernanceTransport = {
  listCandidates: listCapabilityGovernanceCandidates,
  getCandidate: getCapabilityGovernanceCandidate,
  listVerificationTasks: listCapabilityGovernanceVerificationTasks,
  getVerificationTask: getCapabilityGovernanceVerificationTask,
  listPublications: listCapabilityGovernancePublications,
  getPublication: getCapabilityGovernancePublication,
  importCandidates: importCapabilityGovernanceCandidates,
  reviewCandidate: reviewCapabilityGovernanceCandidate,
  publishCatalog: publishCapabilityGovernanceCatalog,
  rollbackCatalog: rollbackCapabilityGovernanceCatalog,
};
