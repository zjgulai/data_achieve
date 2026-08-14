export type CapabilityPlatform =
  | "youtube"
  | "reddit"
  | "x"
  | "instagram"
  | "threads"
  | "tiktok"
  | "linkedin";

export type CapabilityAccessChannel =
  | "official_authorized_api"
  | "licensed_partner_data_service"
  | "public_web_feed"
  | "authorized_browser"
  | "managed_opaque_collector"
  | "authorized_export_import";

export type CapabilityStatus =
  | "unknown"
  | "candidate"
  | "verified"
  | "partial"
  | "blocked"
  | "unsupported"
  | "deprecated";

export type CapabilityResourceType =
  | "content"
  | "conversation"
  | "creator"
  | "topic"
  | "metrics"
  | "media_live"
  | "commerce_ads"
  | "relationship_graph";

export type CapabilityOperation =
  | "resolve_detail"
  | "search_discover"
  | "list_enumerate"
  | "monitor_incremental"
  | "backfill_history"
  | "batch_parse"
  | "export_download";

export type CapabilityMatrixCellDto = {
  platform: CapabilityPlatform;
  access_channel: CapabilityAccessChannel;
  summary_status: CapabilityStatus;
  status_counts: Partial<Record<CapabilityStatus, number>>;
  implementation_ids: string[];
  assertion_ids: string[];
  resource_types: CapabilityResourceType[];
  operations: CapabilityOperation[];
  constraint_codes: string[];
  evidence_count: number;
  last_verified_at: string | null;
};

export type CapabilityMatrixResponseDto = {
  schema_version: "capability_matrix.v1";
  generated_at: string;
  evidence_level: string;
  provider_call: false;
  production_write_allowed: false;
  platforms: CapabilityPlatform[];
  access_channels: CapabilityAccessChannel[];
  cells: CapabilityMatrixCellDto[];
  summary: {
    cell_count: 42;
    populated_cell_count: number;
    unknown_cell_count: number;
    implementation_count: number;
    assertion_count: number;
    evidence_count: number;
  };
};

export type CapabilitySdkSelectionDto = {
  package: string;
  import_name: string | null;
  source_url: string;
  status: "selected" | "candidate" | "manual_review" | "blocked";
  reason: string;
};

export type CapabilityImplementationDto = {
  schema_version: "capability_implementation.v1";
  implementation_id: string;
  provider_id: string;
  platform: CapabilityPlatform;
  access_channel: CapabilityAccessChannel;
  delivery_form: string;
  deployment_mode: string;
  data_domains: string[];
  resource_groups: string[];
  official_docs: string[];
  sdk_selection: CapabilitySdkSelectionDto | null;
  live_adapter_strategy: string;
  auth_mode: string;
  quota_hint: Record<string, unknown>;
  cost_hint: Record<string, unknown>;
  policy_flags: string[];
  blocked_actions: string[];
  stability: "high" | "medium" | "low";
  self_host_priority: string;
  api_version: string;
  required_credentials: string[];
  supported_endpoints: string[];
  lifecycle_status: "active" | "limited" | "deprecated";
};

export type CapabilityAssertionDto = {
  schema_version: "capability_assertion.v1";
  assertion_id: string;
  implementation_id: string;
  resource_type: CapabilityResourceType;
  operation: CapabilityOperation;
  support_status: CapabilityStatus;
  source_resource_group: string;
  region_scope: string[];
  purpose_scope: string[];
  auth_scope: string[];
  field_contract: Record<string, unknown>;
  constraints: Array<{
    constraint_type: string;
    severity: "blocking" | "major" | "minor";
    code: string;
    details: Record<string, unknown>;
  }>;
  score_profile: Record<string, number>;
  evidence_refs: string[];
  last_verified_at: string;
};

export type CapabilityEvidenceDto = {
  schema_version: "capability_evidence.v1";
  evidence_id: string;
  evidence_type: string;
  source_url: string;
  source_version: string;
  observed_at: string;
  content_hash: string;
  hash_scope: "source_reference_only" | "retrieved_content";
  evidence_grade: string;
  provider_call_attempted: false;
  credential_read_attempted: false;
  live_client_created: false;
  production_write_attempted: false;
};

export type CapabilityImplementationDetailDto = {
  schema_version: "capability_implementation_detail.v1";
  implementation: CapabilityImplementationDto;
  assertions: CapabilityAssertionDto[];
  evidence: CapabilityEvidenceDto[];
};

export type CapabilityMatrixCell = {
  platform: CapabilityPlatform;
  accessChannel: CapabilityAccessChannel;
  summaryStatus: CapabilityStatus;
  statusCounts: Partial<Record<CapabilityStatus, number>>;
  implementationIds: string[];
  assertionIds: string[];
  resourceTypes: CapabilityResourceType[];
  operations: CapabilityOperation[];
  constraintCodes: string[];
  evidenceCount: number;
  lastVerifiedAt: string | null;
};

export type CapabilityMatrix = {
  schemaVersion: "capability_matrix.v1";
  generatedAt: string;
  evidenceLevel: string;
  providerCall: false;
  productionWriteAllowed: false;
  platforms: CapabilityPlatform[];
  accessChannels: CapabilityAccessChannel[];
  cells: CapabilityMatrixCell[];
  summary: {
    cellCount: 42;
    populatedCellCount: number;
    unknownCellCount: number;
    implementationCount: number;
    assertionCount: number;
    evidenceCount: number;
  };
};

export type CapabilityImplementation = {
  implementationId: string;
  providerId: string;
  platform: CapabilityPlatform;
  accessChannel: CapabilityAccessChannel;
  deliveryForm: string;
  deploymentMode: string;
  dataDomains: string[];
  resourceGroups: string[];
  officialDocs: string[];
  sdkSelection: CapabilityImplementationDto["sdk_selection"];
  authMode: string;
  quotaHint: Record<string, unknown>;
  costHint: Record<string, unknown>;
  policyFlags: string[];
  blockedActions: string[];
  stability: "high" | "medium" | "low";
  apiVersion: string;
  requiredCredentials: string[];
  supportedEndpoints: string[];
  lifecycleStatus: "active" | "limited" | "deprecated";
};

export type CapabilityAssertion = CapabilityAssertionDto;
export type CapabilityEvidence = CapabilityEvidenceDto;

export type CapabilityImplementationDetail = {
  schemaVersion: "capability_implementation_detail.v1";
  implementation: CapabilityImplementation;
  assertions: CapabilityAssertion[];
  evidence: CapabilityEvidence[];
};

export type CapabilityImplementationFilters = {
  platform?: CapabilityPlatform;
  accessChannel?: CapabilityAccessChannel;
};

export type CapabilityAssertionFilters = CapabilityImplementationFilters & {
  resourceType?: CapabilityResourceType;
  operation?: CapabilityOperation;
  supportStatus?: CapabilityStatus;
};
