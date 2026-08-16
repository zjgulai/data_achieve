import type {
  CapabilityAccessChannel,
  CapabilityAssertionDto,
  CapabilityEvidenceDto,
  CapabilityImplementationDto,
  CapabilityOperation,
  CapabilityPlatform,
  CapabilityResourceType,
  CapabilityStatus,
} from "@/types/capability";
import type {
  CapabilityDiscoveryConstraintDto,
  CapabilityDiscoveryDeliveryForm,
  CapabilityDiscoveryDeploymentMode,
  CapabilityDiscoveryFixtureId,
  CapabilityDiscoveryParserId,
} from "@/types/capability-discovery";

export type CapabilityGovernancePermissionSetDto = {
  can_read: boolean;
  can_review: boolean;
  can_publish: boolean;
};

export type CapabilityGovernancePermissionSet = {
  canRead: boolean;
  canReview: boolean;
  canPublish: boolean;
};

export type CapabilityGovernanceProposedImplementationDto = {
  schema_version: "capability_proposed_implementation_preview.v1";
  proposed_implementation_id: string;
  provider_id: string;
  platform: CapabilityPlatform;
  access_channel: CapabilityAccessChannel;
  delivery_form: CapabilityDiscoveryDeliveryForm;
  deployment_mode: CapabilityDiscoveryDeploymentMode;
  source_label: string;
  claimed_auth_mode: string;
  claimed_required_credentials: string[];
  claimed_limitations: string[];
};

export type CapabilityGovernanceCandidateAssertionDto = {
  schema_version: "capability_candidate_assertion_preview.v1";
  candidate_id: string;
  proposed_implementation_id: string;
  platform: CapabilityPlatform;
  access_channel: CapabilityAccessChannel;
  resource_type: CapabilityResourceType;
  operation: CapabilityOperation;
  support_status: "candidate";
  verification_status: "unverified";
  executable: false;
  publishable: false;
  claimed_field_contract: Record<string, unknown>;
  claimed_constraints: CapabilityDiscoveryConstraintDto[];
  region_scope: string[];
  purpose_scope: string[];
  auth_scope: string[];
  parser_id: CapabilityDiscoveryParserId;
  candidate_fingerprint: string;
};

export type CapabilityGovernanceCandidateDto = {
  id: string;
  candidate_key: string;
  semantic_version: number;
  candidate_fingerprint: string;
  predecessor_id: string | null;
  proposed_implementation: CapabilityGovernanceProposedImplementationDto;
  candidate_assertion: CapabilityGovernanceCandidateAssertionDto;
  first_seen_batch_id: string;
  created_at: string;
};

export type CapabilityGovernanceVerificationTaskType =
  | "initial_review"
  | "evidence_refresh"
  | "semantic_drift";
export type CapabilityGovernanceVerificationTaskStatus = "open" | "resolved";
export type CapabilityGovernanceVerificationAction =
  | "verify"
  | "reject"
  | "deprecate";

export type CapabilityGovernanceVerificationTaskDto = {
  id: string;
  candidate_version_id: string;
  task_type: CapabilityGovernanceVerificationTaskType;
  status: CapabilityGovernanceVerificationTaskStatus;
  task_version: number;
  opened_at: string;
  resolved_at: string | null;
  decision_id: string | null;
};

export type CapabilityGovernanceDecisionDto = {
  id: string;
  verification_task_id: string;
  candidate_version_id: string;
  action: CapabilityGovernanceVerificationAction;
  verification_status: "verified" | "rejected";
  reviewer_user_id: string;
  reviewed_at: string;
  reason: string;
  canonical_bundle: Record<string, unknown> | null;
};

export type CapabilityGovernancePublicationRevisionDto = {
  id: string;
  revision_number: number;
  parent_revision_id: string | null;
  restored_from_revision_id: string | null;
  catalog_snapshot_id: string;
  publisher_user_id: string;
  published_at: string;
  reason: string;
  operations: Array<Record<string, unknown>>;
  is_current: boolean;
};

export type CapabilityGovernanceCandidateListResponseDto = {
  schema_version: "capability_governance_candidate_list.v1";
  permissions: CapabilityGovernancePermissionSetDto;
  items: CapabilityGovernanceCandidateDto[];
  limit: number;
  offset: number;
};

export type CapabilityGovernanceCandidateDetailResponseDto = {
  schema_version: "capability_governance_candidate_detail.v1";
  candidate: CapabilityGovernanceCandidateDto;
  evidence: CapabilityEvidenceDto[];
  open_verification_task: CapabilityGovernanceVerificationTaskDto | null;
  latest_decision: CapabilityGovernanceDecisionDto | null;
};

export type CapabilityGovernanceVerificationTaskListResponseDto = {
  schema_version: "capability_governance_verification_task_list.v1";
  items: CapabilityGovernanceVerificationTaskDto[];
  limit: number;
  offset: number;
};

export type CapabilityGovernanceVerificationTaskDetailResponseDto = {
  schema_version: "capability_governance_verification_task_detail.v1";
  task: CapabilityGovernanceVerificationTaskDto;
  candidate: CapabilityGovernanceCandidateDto;
  evidence: CapabilityEvidenceDto[];
  decision: CapabilityGovernanceDecisionDto | null;
};

export type CapabilityGovernancePublicationListResponseDto = {
  schema_version: "capability_governance_publication_list.v1";
  items: CapabilityGovernancePublicationRevisionDto[];
  current_revision_id: string | null;
  limit: number;
  offset: number;
};

export type CapabilityGovernancePublicationDetailResponseDto = {
  schema_version: "capability_governance_publication_detail.v1";
  revision: CapabilityGovernancePublicationRevisionDto;
  current_revision_id: string | null;
};

export type CapabilityGovernanceImportRequestDto = {
  schema_version: "capability_governance_import_request.v1";
  fixture_ids: CapabilityDiscoveryFixtureId[];
  expected_preview_fingerprint: string;
};

export type CapabilityGovernanceCanonicalAssertionDto = Omit<
  CapabilityAssertionDto,
  "schema_version" | "last_verified_at"
> & {
  support_status: Exclude<CapabilityStatus, "unknown" | "candidate">;
};

type CapabilityGovernanceReviewRequestBaseDto = {
  schema_version: "capability_governance_review_request.v1";
  expected_task_version: number;
  reason: string;
};

export type CapabilityGovernanceRejectRequestDto =
  CapabilityGovernanceReviewRequestBaseDto & {
    action: "reject";
    canonical_implementation: null;
    canonical_assertion: null;
  };

export type CapabilityGovernanceVerifiedReviewRequestDto =
  CapabilityGovernanceReviewRequestBaseDto & {
    action: "verify" | "deprecate";
    canonical_implementation: CapabilityImplementationDto;
    canonical_assertion: CapabilityGovernanceCanonicalAssertionDto;
  };

export type CapabilityGovernanceReviewRequestDto =
  | CapabilityGovernanceRejectRequestDto
  | CapabilityGovernanceVerifiedReviewRequestDto;

export type CapabilityGovernancePublicationOperationDto =
  | {
      operation: "upsert_verified_assertion";
      verification_decision_id: string;
    }
  | {
      operation: "remove_assertion";
      verification_decision_id: string;
      logical_assertion_key: string;
    };

export type CapabilityGovernancePublicationRequestDto = {
  schema_version: "capability_governance_publication_request.v1";
  expected_parent_revision_id: string | null;
  reason: string;
  operations: CapabilityGovernancePublicationOperationDto[];
};

export type CapabilityGovernanceRollbackRequestDto = {
  schema_version: "capability_governance_rollback_request.v1";
  expected_current_revision_id: string;
  target_revision_id: string;
  reason: string;
};

export type CapabilityGovernanceWriteAttemptDto = {
  database_write: boolean;
  domain_changed: boolean;
  idempotent_replay: boolean;
  provider_call: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  workflow_run_created: false;
  database_migration: false;
  production_write_allowed: false;
};

export type CapabilityGovernanceImportResponseDto =
  CapabilityGovernanceWriteAttemptDto & {
    schema_version: "capability_governance_import_response.v1";
    request_id: string;
    batch_id: string | null;
    preview_fingerprint: string;
    outcome:
      | "first_observation"
      | "semantic_exact_replay"
      | "evidence_refresh"
      | "semantic_drift"
      | "mixed";
    candidates: Array<{
      candidate_key: string;
      candidate_version_id: string;
      semantic_version: number;
      classification:
        | "first_observation"
        | "semantic_exact_replay"
        | "evidence_refresh"
        | "semantic_drift";
      verification_task_id: string | null;
      evidence_added_count: number;
    }>;
  };

export type CapabilityGovernanceReviewResponseDto =
  CapabilityGovernanceWriteAttemptDto & {
    schema_version: "capability_governance_review_response.v1";
    request_id: string;
    decision_id: string;
    task_id: string;
    candidate_version_id: string;
    task_version: number;
    action: CapabilityGovernanceVerificationAction;
    verification_status: "verified" | "rejected";
    reviewed_at: string;
  };

export type CapabilityGovernancePublicationResponseDto =
  CapabilityGovernanceWriteAttemptDto & {
    schema_version: "capability_governance_publication_response.v1";
    publication_kind: "publish" | "rollback";
    request_id: string;
    revision_id: string;
    revision_number: number;
    parent_revision_id: string | null;
    restored_from_revision_id: string | null;
    catalog_snapshot_id: string;
    head_version: number;
    operation_count: number;
    published_at: string;
  };

export type CapabilityGovernanceProposedImplementation = {
  schemaVersion: CapabilityGovernanceProposedImplementationDto["schema_version"];
  proposedImplementationId: string;
  providerId: string;
  platform: CapabilityPlatform;
  accessChannel: CapabilityAccessChannel;
  deliveryForm: CapabilityDiscoveryDeliveryForm;
  deploymentMode: CapabilityDiscoveryDeploymentMode;
  sourceLabel: string;
  claimedAuthMode: string;
  claimedRequiredCredentials: string[];
  claimedLimitations: string[];
};

export type CapabilityGovernanceCandidateAssertion = {
  schemaVersion: CapabilityGovernanceCandidateAssertionDto["schema_version"];
  candidateId: string;
  proposedImplementationId: string;
  platform: CapabilityPlatform;
  accessChannel: CapabilityAccessChannel;
  resourceType: CapabilityResourceType;
  operation: CapabilityOperation;
  supportStatus: "candidate";
  verificationStatus: "unverified";
  executable: false;
  publishable: false;
  claimedFieldContract: Record<string, unknown>;
  claimedConstraints: CapabilityDiscoveryConstraintDto[];
  regionScope: string[];
  purposeScope: string[];
  authScope: string[];
  parserId: CapabilityDiscoveryParserId;
  candidateFingerprint: string;
};

export type CapabilityGovernanceCandidate = {
  id: string;
  candidateKey: string;
  semanticVersion: number;
  candidateFingerprint: string;
  predecessorId: string | null;
  proposedImplementation: CapabilityGovernanceProposedImplementation;
  candidateAssertion: CapabilityGovernanceCandidateAssertion;
  firstSeenBatchId: string;
  createdAt: string;
};

export type CapabilityGovernanceVerificationTask = {
  id: string;
  candidateVersionId: string;
  taskType: CapabilityGovernanceVerificationTaskType;
  status: CapabilityGovernanceVerificationTaskStatus;
  taskVersion: number;
  openedAt: string;
  resolvedAt: string | null;
  decisionId: string | null;
};

export type CapabilityGovernanceDecision = {
  id: string;
  verificationTaskId: string;
  candidateVersionId: string;
  action: CapabilityGovernanceVerificationAction;
  verificationStatus: "verified" | "rejected";
  reviewerUserId: string;
  reviewedAt: string;
  reason: string;
  canonicalBundle: Record<string, unknown> | null;
};

export type CapabilityGovernancePublicationRevision = {
  id: string;
  revisionNumber: number;
  parentRevisionId: string | null;
  restoredFromRevisionId: string | null;
  catalogSnapshotId: string;
  publisherUserId: string;
  publishedAt: string;
  reason: string;
  operations: Array<Record<string, unknown>>;
  isCurrent: boolean;
};

export type CapabilityGovernanceCandidateList = {
  schemaVersion: CapabilityGovernanceCandidateListResponseDto["schema_version"];
  permissions: CapabilityGovernancePermissionSet;
  items: CapabilityGovernanceCandidate[];
  limit: number;
  offset: number;
};

export type CapabilityGovernanceCandidateDetail = {
  schemaVersion: CapabilityGovernanceCandidateDetailResponseDto["schema_version"];
  candidate: CapabilityGovernanceCandidate;
  evidence: CapabilityEvidenceDto[];
  openVerificationTask: CapabilityGovernanceVerificationTask | null;
  latestDecision: CapabilityGovernanceDecision | null;
};

export type CapabilityGovernanceVerificationTaskList = {
  schemaVersion: CapabilityGovernanceVerificationTaskListResponseDto["schema_version"];
  items: CapabilityGovernanceVerificationTask[];
  limit: number;
  offset: number;
};

export type CapabilityGovernanceVerificationTaskDetail = {
  schemaVersion: CapabilityGovernanceVerificationTaskDetailResponseDto["schema_version"];
  task: CapabilityGovernanceVerificationTask;
  candidate: CapabilityGovernanceCandidate;
  evidence: CapabilityEvidenceDto[];
  decision: CapabilityGovernanceDecision | null;
};

export type CapabilityGovernancePublicationList = {
  schemaVersion: CapabilityGovernancePublicationListResponseDto["schema_version"];
  items: CapabilityGovernancePublicationRevision[];
  currentRevisionId: string | null;
  limit: number;
  offset: number;
};

export type CapabilityGovernancePublicationDetail = {
  schemaVersion: CapabilityGovernancePublicationDetailResponseDto["schema_version"];
  revision: CapabilityGovernancePublicationRevision;
  currentRevisionId: string | null;
};

export type CapabilityGovernanceImportResponse = {
  schemaVersion: CapabilityGovernanceImportResponseDto["schema_version"];
  requestId: string;
  batchId: string | null;
  previewFingerprint: string;
  outcome: CapabilityGovernanceImportResponseDto["outcome"];
  candidates: Array<{
    candidateKey: string;
    candidateVersionId: string;
    semanticVersion: number;
    classification: CapabilityGovernanceImportResponseDto["candidates"][number]["classification"];
    verificationTaskId: string | null;
    evidenceAddedCount: number;
  }>;
  databaseWrite: boolean;
  domainChanged: boolean;
  idempotentReplay: boolean;
};

export type CapabilityGovernanceReviewResponse = {
  schemaVersion: CapabilityGovernanceReviewResponseDto["schema_version"];
  requestId: string;
  decisionId: string;
  taskId: string;
  candidateVersionId: string;
  taskVersion: number;
  action: CapabilityGovernanceVerificationAction;
  verificationStatus: "verified" | "rejected";
  reviewedAt: string;
  databaseWrite: boolean;
  domainChanged: boolean;
  idempotentReplay: boolean;
};

export type CapabilityGovernancePublicationResponse = {
  schemaVersion: CapabilityGovernancePublicationResponseDto["schema_version"];
  publicationKind: "publish" | "rollback";
  requestId: string;
  revisionId: string;
  revisionNumber: number;
  parentRevisionId: string | null;
  restoredFromRevisionId: string | null;
  catalogSnapshotId: string;
  headVersion: number;
  operationCount: number;
  publishedAt: string;
  databaseWrite: boolean;
  domainChanged: boolean;
  idempotentReplay: boolean;
};

export type CapabilityGovernanceReviewInput =
  | {
      expectedTaskVersion: number;
      action: "reject";
      reason: string;
    }
  | {
      expectedTaskVersion: number;
      action: "verify" | "deprecate";
      reason: string;
      canonicalImplementation: CapabilityImplementationDto;
      canonicalAssertion: CapabilityGovernanceCanonicalAssertionDto;
    };

export type CapabilityGovernancePublicationOperationInput =
  | {
      operation: "upsert_verified_assertion";
      verificationDecisionId: string;
    }
  | {
      operation: "remove_assertion";
      verificationDecisionId: string;
      logicalAssertionKey: string;
    };
