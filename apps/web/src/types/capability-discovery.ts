export type CapabilityDiscoveryFixtureId =
  | "tikhub-youtube-market-v1"
  | "apify-reddit-market-v1"
  | "youtube-data-api-doc-v1"
  | "reddit-data-api-doc-v1";

export type CapabilityDiscoveryParserId =
  | "tikhub_public_market.v1"
  | "apify_public_market.v1"
  | "youtube_official_doc.v1"
  | "reddit_official_doc.v1";

export type CapabilityDiscoveryPlatform =
  | "youtube"
  | "reddit"
  | "x"
  | "instagram"
  | "threads"
  | "tiktok"
  | "linkedin";

export type CapabilityDiscoveryAccessChannel =
  | "official_authorized_api"
  | "licensed_partner_data_service"
  | "public_web_feed"
  | "authorized_browser"
  | "managed_opaque_collector"
  | "authorized_export_import";

export type CapabilityDiscoveryDeliveryForm =
  | "endpoint"
  | "sdk"
  | "actor"
  | "collector"
  | "parser"
  | "workflow"
  | "skill"
  | "mcp"
  | "agent";

export type CapabilityDiscoveryDeploymentMode =
  | "official_cloud"
  | "managed_saas"
  | "byok"
  | "self_hosted"
  | "browser_runtime"
  | "manual_import";

export type CapabilityDiscoveryResourceType =
  | "content"
  | "conversation"
  | "creator"
  | "topic"
  | "metrics"
  | "media_live"
  | "commerce_ads"
  | "relationship_graph";

export type CapabilityDiscoveryOperation =
  | "resolve_detail"
  | "search_discover"
  | "list_enumerate"
  | "monitor_incremental"
  | "backfill_history"
  | "batch_parse"
  | "export_download";

export type CapabilityDiscoveryConstraintDto = {
  constraint_type: "policy" | "blocked_action" | "quota" | "purpose" | "region";
  severity: "blocking" | "major" | "minor";
  code: string;
  details: Record<string, unknown>;
};

export type CapabilityDiscoverySourceSnapshotDto = {
  schema_version: "capability_source_snapshot_preview.v1";
  fixture_id: string;
  source_kind: "public_market" | "official_doc";
  source_name: string;
  source_url: string;
  source_version: string;
  observed_at: string;
  parser_id: CapabilityDiscoveryParserId;
  content_hash: string;
};

export type CapabilityDiscoveryProposedImplementationDto = {
  schema_version: "capability_proposed_implementation_preview.v1";
  proposed_implementation_id: string;
  provider_id: string;
  platform: CapabilityDiscoveryPlatform;
  access_channel: CapabilityDiscoveryAccessChannel;
  delivery_form: CapabilityDiscoveryDeliveryForm;
  deployment_mode: CapabilityDiscoveryDeploymentMode;
  source_label: string;
  claimed_auth_mode: string;
  claimed_required_credentials: string[];
  claimed_limitations: string[];
  evidence_refs: string[];
};

export type CapabilityDiscoveryCandidateAssertionDto = {
  schema_version: "capability_candidate_assertion_preview.v1";
  candidate_id: string;
  proposed_implementation_id: string;
  platform: CapabilityDiscoveryPlatform;
  access_channel: CapabilityDiscoveryAccessChannel;
  resource_type: CapabilityDiscoveryResourceType;
  operation: CapabilityDiscoveryOperation;
  support_status: "candidate";
  verification_status: "unverified";
  executable: false;
  publishable: false;
  claimed_field_contract: Record<string, unknown>;
  claimed_constraints: CapabilityDiscoveryConstraintDto[];
  region_scope: string[];
  purpose_scope: string[];
  auth_scope: string[];
  source_claim_refs: string[];
  evidence_refs: string[];
  parser_id: CapabilityDiscoveryParserId;
  candidate_fingerprint: string;
};

export type CapabilityDiscoveryEvidenceDto = {
  schema_version: "capability_evidence.v1";
  evidence_id: string;
  evidence_type:
    | "official_doc"
    | "public_market"
    | "repository"
    | "fixture"
    | "authorized_runtime";
  source_url: string;
  source_version: string;
  observed_at: string;
  content_hash: string;
  hash_scope: "retrieved_content";
  evidence_grade: "L2-fixture-or-dry-run";
  provider_call_attempted: false;
  credential_read_attempted: false;
  live_client_created: false;
  production_write_attempted: false;
};

export type CapabilityDiscoveryDiagnosticDto = {
  schema_version: "capability_discovery_diagnostic.v1";
  fixture_id: string;
  severity: "info" | "warning" | "error";
  code: string;
  message: string;
  source_claim_ref: string;
};

export type CapabilityDiscoverySummaryDto = {
  source_count: number;
  market_source_count: number;
  official_doc_source_count: number;
  proposed_implementation_count: number;
  candidate_assertion_count: number;
  evidence_count: number;
  warning_count: number;
  error_count: 0;
};

export type CapabilityDiscoveryPreviewRequestDto = {
  schema_version: "capability_discovery_preview_request.v1";
  preview_mode: "fixture_replay";
  fixture_ids: CapabilityDiscoveryFixtureId[];
};

export type CapabilityDiscoveryPreviewResponseDto = {
  schema_version: "capability_discovery_preview.v1";
  evidence_grade: "L2-fixture-or-dry-run";
  preview_mode: "fixture_replay";
  preview_fingerprint: string;
  generated_from_observed_at: string;
  source_snapshots: CapabilityDiscoverySourceSnapshotDto[];
  proposed_implementations: CapabilityDiscoveryProposedImplementationDto[];
  candidate_assertions: CapabilityDiscoveryCandidateAssertionDto[];
  evidence: CapabilityDiscoveryEvidenceDto[];
  diagnostics: CapabilityDiscoveryDiagnosticDto[];
  summary: CapabilityDiscoverySummaryDto;
  provider_call: false;
  provider_call_attempted: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  credential_read_attempted: false;
  database_write: false;
  database_migration: false;
  workflow_run_created: false;
  candidate_publish_allowed: false;
  production_write_allowed: false;
};

export type CapabilityDiscoveryConstraint = {
  constraintType: CapabilityDiscoveryConstraintDto["constraint_type"];
  severity: CapabilityDiscoveryConstraintDto["severity"];
  code: string;
  details: Record<string, unknown>;
};

export type CapabilityDiscoverySourceSnapshot = {
  schemaVersion: CapabilityDiscoverySourceSnapshotDto["schema_version"];
  fixtureId: string;
  sourceKind: CapabilityDiscoverySourceSnapshotDto["source_kind"];
  sourceName: string;
  sourceUrl: string;
  sourceVersion: string;
  observedAt: string;
  parserId: CapabilityDiscoveryParserId;
  contentHash: string;
};

export type CapabilityDiscoveryProposedImplementation = {
  schemaVersion: CapabilityDiscoveryProposedImplementationDto["schema_version"];
  proposedImplementationId: string;
  providerId: string;
  platform: CapabilityDiscoveryPlatform;
  accessChannel: CapabilityDiscoveryAccessChannel;
  deliveryForm: CapabilityDiscoveryDeliveryForm;
  deploymentMode: CapabilityDiscoveryDeploymentMode;
  sourceLabel: string;
  claimedAuthMode: string;
  claimedRequiredCredentials: string[];
  claimedLimitations: string[];
  evidenceRefs: string[];
};

export type CapabilityDiscoveryCandidateAssertion = {
  schemaVersion: CapabilityDiscoveryCandidateAssertionDto["schema_version"];
  candidateId: string;
  proposedImplementationId: string;
  platform: CapabilityDiscoveryPlatform;
  accessChannel: CapabilityDiscoveryAccessChannel;
  resourceType: CapabilityDiscoveryResourceType;
  operation: CapabilityDiscoveryOperation;
  supportStatus: "candidate";
  verificationStatus: "unverified";
  executable: false;
  publishable: false;
  claimedFieldContract: Record<string, unknown>;
  claimedConstraints: CapabilityDiscoveryConstraint[];
  regionScope: string[];
  purposeScope: string[];
  authScope: string[];
  sourceClaimRefs: string[];
  evidenceRefs: string[];
  parserId: CapabilityDiscoveryParserId;
  candidateFingerprint: string;
};

export type CapabilityDiscoveryEvidence = {
  schemaVersion: CapabilityDiscoveryEvidenceDto["schema_version"];
  evidenceId: string;
  evidenceType: CapabilityDiscoveryEvidenceDto["evidence_type"];
  sourceUrl: string;
  sourceVersion: string;
  observedAt: string;
  contentHash: string;
  hashScope: "retrieved_content";
  evidenceGrade: "L2-fixture-or-dry-run";
  providerCallAttempted: false;
  credentialReadAttempted: false;
  liveClientCreated: false;
  productionWriteAttempted: false;
};

export type CapabilityDiscoveryDiagnostic = {
  schemaVersion: CapabilityDiscoveryDiagnosticDto["schema_version"];
  fixtureId: string;
  severity: CapabilityDiscoveryDiagnosticDto["severity"];
  code: string;
  message: string;
  sourceClaimRef: string;
};

export type CapabilityDiscoverySummary = {
  sourceCount: number;
  marketSourceCount: number;
  officialDocSourceCount: number;
  proposedImplementationCount: number;
  candidateAssertionCount: number;
  evidenceCount: number;
  warningCount: number;
  errorCount: 0;
};

export type CapabilityDiscoveryPreview = {
  schemaVersion: CapabilityDiscoveryPreviewResponseDto["schema_version"];
  evidenceGrade: "L2-fixture-or-dry-run";
  previewMode: "fixture_replay";
  previewFingerprint: string;
  generatedFromObservedAt: string;
  sourceSnapshots: CapabilityDiscoverySourceSnapshot[];
  proposedImplementations: CapabilityDiscoveryProposedImplementation[];
  candidateAssertions: CapabilityDiscoveryCandidateAssertion[];
  evidence: CapabilityDiscoveryEvidence[];
  diagnostics: CapabilityDiscoveryDiagnostic[];
  summary: CapabilityDiscoverySummary;
  providerCall: false;
  providerCallAttempted: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  credentialReadAttempted: false;
  databaseWrite: false;
  databaseMigration: false;
  workflowRunCreated: false;
  candidatePublishAllowed: false;
  productionWriteAllowed: false;
};
