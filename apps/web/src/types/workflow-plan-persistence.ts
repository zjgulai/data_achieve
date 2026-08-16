import type { CapabilityPlatform } from "@/types/capability";
import type { ProjectStatus } from "@/types/project";
import type {
  BatchPlanningInputDto,
  PlannerJsonValue,
  PeriodicPlanningInputDto,
  PlanningInput,
  PlanningInputDto,
  WorkflowPlanPreview,
  WorkflowPlanPreviewDto,
  WorkflowPlannerMatchMode,
  WorkflowPlannerMode,
  WorkflowPlanningStatus,
  MonitoringScopeType,
} from "@/types/workflow-planner";

export type WorkflowPlanStatus =
  | "draft"
  | "previewed"
  | "approved"
  | "active"
  | "paused"
  | "archived";
export type WorkflowPlanSaveOutcome = "created" | "semantic_no_op";

export type ApiRequestOptions = {
  signal?: AbortSignal;
};

export type PaginationOptions = ApiRequestOptions & {
  limit?: number;
  offset?: number;
};

export type WorkflowPlanCreateInput = {
  name: string;
  previewInput: PlanningInput;
  expectedPreviewFingerprint: string;
  idempotencyKey: string;
};

export type WorkflowPlanCloneInput = {
  name: string;
  sourceVersionId: string;
  idempotencyKey: string;
};

export type MonitoringScopeTemplateCopyInput = {
  sourceVersionId: string;
  idempotencyKey: string;
};

export type WorkflowVersionCreateInput = {
  previewInput: PlanningInput;
  expectedPreviewFingerprint: string;
  expectedCurrentVersionId: string;
  idempotencyKey: string;
};

export type WorkflowPlanTransitionInput = {
  expectedStatus: WorkflowPlanStatus;
  toStatus: WorkflowPlanStatus;
  reason?: string | null;
};

export type WorkflowTemplateCreateInput = {
  name: string;
  templateKey: string;
  description?: string | null;
  definition: PlanningInput;
  idempotencyKey: string;
};

export type WorkflowTemplateMetadataUpdateInput = {
  expectedRevisionId: string;
  name?: string;
  description?: string | null;
  idempotencyKey: string;
};

export type WorkflowTemplateRevisionCreateInput = {
  expectedRevisionId: string;
  definition: PlanningInput;
  idempotencyKey: string;
};

export type WorkflowTemplateInstantiateInput = {
  revisionId: string;
  name: string;
  idempotencyKey: string;
};

export type WorkflowPlanCreateRequestDto = {
  name: string;
  preview_input: PlanningInputDto;
  expected_preview_fingerprint: string;
};

export type WorkflowVersionCreateRequestDto = {
  preview_input: PlanningInputDto;
  expected_preview_fingerprint: string;
  expected_current_version_id: string;
};

export type WorkflowPlanTransitionRequestDto = {
  expected_status: WorkflowPlanStatus;
  to_status: WorkflowPlanStatus;
  reason?: string | null;
};

export type WorkflowTemplateCreateRequestDto = {
  name: string;
  template_key: string;
  description?: string | null;
  definition: PlanningInputDto;
};

export type WorkflowTemplateMetadataUpdateRequestDto = {
  expected_revision_id: string;
  name?: string;
  description?: string | null;
};

export type WorkflowTemplateRevisionCreateRequestDto = {
  expected_revision_id: string;
  definition: PlanningInputDto;
};

export type WorkflowTemplateInstantiateRequestDto = {
  revision_id: string;
  name: string;
};

export type WorkflowPlanCloneRequestDto = {
  name: string;
  source_version_id: string;
};

export type MonitoringScopeTemplateCopyRequestDto = {
  source_version_id: string;
};

export type WorkflowExecutionBoundaryDto = {
  provider_call: false;
  actor_run: false;
  browser_run: false;
  llm_call: false;
  workflow_run_created: false;
  execution_authorized: false;
};

export type WorkflowExecutionBoundary = {
  providerCall: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  workflowRunCreated: false;
  executionAuthorized: false;
};

export type WorkflowPlanReadBoundaryDto = WorkflowExecutionBoundaryDto & {
  database_write: false;
  plan_changed: false;
};

export type WorkflowPlanReadBoundary = WorkflowExecutionBoundary & {
  databaseWrite: false;
  planChanged: false;
};

export type WorkflowPlanDto = {
  id: string;
  workspace_id: string;
  project_id: string;
  created_by_user_id: string;
  name: string;
  flow_mode: WorkflowPlannerMode;
  status: WorkflowPlanStatus;
  current_version_id: string;
  source_plan_id?: string | null;
  source_version_id?: string | null;
  workflow_template_id?: string | null;
  workflow_template_revision_id?: string | null;
  current_version_number: number;
  planning_status: WorkflowPlanningStatus;
  scope_count: number;
  query_term_count: number;
  created_at: string;
  updated_at: string;
};

export type WorkflowPlan = {
  id: string;
  workspaceId: string;
  projectId: string;
  createdByUserId: string;
  name: string;
  flowMode: WorkflowPlannerMode;
  status: WorkflowPlanStatus;
  currentVersionId: string;
  sourcePlanId?: string | null;
  sourceVersionId?: string | null;
  workflowTemplateId?: string | null;
  workflowTemplateRevisionId?: string | null;
  currentVersionNumber: number;
  planningStatus: WorkflowPlanningStatus;
  scopeCount: number;
  queryTermCount: number;
  createdAt: string;
  updatedAt: string;
};

export type WorkflowVersionSummaryDto = {
  id: string;
  workspace_id: string;
  project_id: string;
  workflow_plan_id: string;
  workflow_template_id?: string | null;
  workflow_template_revision_id?: string | null;
  created_by_user_id: string;
  version_number: number;
  planning_status: WorkflowPlanningStatus;
  planner_contract_version: string;
  catalog_snapshot_id: string;
  policy_version: string;
  mode_template_version: string;
  query_versions: Partial<Record<CapabilityPlatform, string>>;
  preview_fingerprint: string;
  created_at: string;
};

export type WorkflowVersionSummary = {
  id: string;
  workspaceId: string;
  projectId: string;
  workflowPlanId: string;
  workflowTemplateId?: string | null;
  workflowTemplateRevisionId?: string | null;
  createdByUserId: string;
  versionNumber: number;
  planningStatus: WorkflowPlanningStatus;
  plannerContractVersion: string;
  catalogSnapshotId: string;
  policyVersion: string;
  modeTemplateVersion: string;
  queryVersions: Partial<Record<CapabilityPlatform, string>>;
  previewFingerprint: string;
  createdAt: string;
};

export type WorkflowVersionDto = WorkflowVersionSummaryDto & {
  editable_input:
    | PeriodicPlanningInputDto
    | (Omit<BatchPlanningInputDto, "schedule_intent"> & {
        schedule_intent?: null;
      });
  preview: WorkflowPlanPreviewDto;
};

export type WorkflowVersion = WorkflowVersionSummary & {
  editableInput: PlanningInput;
  preview: WorkflowPlanPreview;
};

export type WorkflowPlanCloneResultDto = WorkflowExecutionBoundaryDto & {
  database_write: boolean;
  plan_changed: boolean;
  outcome: "created";
  idempotent_replay: boolean;
  source_plan_id: string;
  source_version_id: string;
  plan: WorkflowPlanDto;
  version: WorkflowVersionDto;
};

export type WorkflowPlanCloneResult = WorkflowExecutionBoundary & {
  databaseWrite: boolean;
  planChanged: boolean;
  outcome: "created";
  idempotentReplay: boolean;
  sourcePlanId: string;
  sourceVersionId: string;
  plan: WorkflowPlan;
  version: WorkflowVersion;
};

export type MonitoringScopeDto = {
  id: string;
  workspace_id: string;
  project_id: string;
  created_by_user_id: string;
  scope_key: string;
  scope_type: MonitoringScopeType;
  canonical_term: string | null;
  aliases: string[];
  include_terms: string[];
  exclude_terms: string[];
  official_accounts: string[];
  seed_urls: string[];
  effective_languages: string[];
  effective_regions: string[];
  effective_platforms: CapabilityPlatform[];
  match_mode: WorkflowPlannerMatchMode;
  created_at: string;
};

export type MonitoringScope = {
  id: string;
  workspaceId: string;
  projectId: string;
  createdByUserId: string;
  scopeKey: string;
  scopeType: MonitoringScopeType;
  canonicalTerm: string | null;
  aliases: string[];
  includeTerms: string[];
  excludeTerms: string[];
  officialAccounts: string[];
  seedUrls: string[];
  effectiveLanguages: string[];
  effectiveRegions: string[];
  effectivePlatforms: CapabilityPlatform[];
  matchMode: WorkflowPlannerMatchMode;
  createdAt: string;
};

export type MonitoringScopeTemplateDto = WorkflowExecutionBoundaryDto & {
  id: string;
  workspace_id: string;
  project_id: string;
  created_by_user_id: string;
  source_scope_id: string;
  source_plan_id: string;
  source_version_id: string;
  scope_key: string;
  scope_type: MonitoringScopeType;
  canonical_term: string | null;
  aliases: string[];
  include_terms: string[];
  exclude_terms: string[];
  official_accounts: string[];
  seed_urls: string[];
  effective_languages: string[];
  effective_regions: string[];
  effective_platforms: CapabilityPlatform[];
  match_mode: WorkflowPlannerMatchMode;
  created_at: string;
};

export type MonitoringScopeTemplate = {
  providerCall: false;
  actorRun: false;
  browserRun: false;
  llmCall: false;
  workflowRunCreated: false;
  executionAuthorized: false;
  id: string;
  workspaceId: string;
  projectId: string;
  createdByUserId: string;
  sourceScopeId: string;
  sourcePlanId: string;
  sourceVersionId: string;
  scopeKey: string;
  scopeType: MonitoringScopeType;
  canonicalTerm: string | null;
  aliases: string[];
  includeTerms: string[];
  excludeTerms: string[];
  officialAccounts: string[];
  seedUrls: string[];
  effectiveLanguages: string[];
  effectiveRegions: string[];
  effectivePlatforms: CapabilityPlatform[];
  matchMode: WorkflowPlannerMatchMode;
  createdAt: string;
};

export type MonitoringScopeTemplateCopyResultDto = WorkflowExecutionBoundaryDto & {
  database_write: boolean;
  idempotent_replay: boolean;
  template: MonitoringScopeTemplateDto;
};

export type MonitoringScopeTemplateCopyResult = WorkflowExecutionBoundary & {
  databaseWrite: boolean;
  idempotentReplay: boolean;
  template: MonitoringScopeTemplate;
};

export type WorkflowPlanSaveResultDto = WorkflowExecutionBoundaryDto & {
  database_write: boolean;
  plan_changed: boolean;
  outcome: WorkflowPlanSaveOutcome;
  idempotent_replay: boolean;
  plan: WorkflowPlanDto;
  version: WorkflowVersionDto;
};

export type WorkflowPlanSaveResult = WorkflowExecutionBoundary & {
  databaseWrite: boolean;
  planChanged: boolean;
  outcome: WorkflowPlanSaveOutcome;
  idempotentReplay: boolean;
  plan: WorkflowPlan;
  version: WorkflowVersion;
};

export type WorkflowPlanTransitionResultDto = WorkflowExecutionBoundaryDto & {
  database_write: boolean;
  plan_changed: boolean;
  idempotent_replay: false;
  from_status: WorkflowPlanStatus;
  to_status: WorkflowPlanStatus;
  reason: string | null;
  plan: WorkflowPlanDto;
};

export type WorkflowPlanTransitionResult = WorkflowExecutionBoundary & {
  databaseWrite: boolean;
  planChanged: boolean;
  idempotentReplay: false;
  fromStatus: WorkflowPlanStatus;
  toStatus: WorkflowPlanStatus;
  reason: string | null;
  plan: WorkflowPlan;
};

export type WorkflowTemplateStatus = WorkflowPlanStatus;

export type WorkflowTemplateRevisionDto = WorkflowExecutionBoundaryDto & {
  id: string;
  workspace_id: string;
  project_id: string;
  workflow_template_id: string;
  created_by_user_id: string;
  revision_number: number;
  definition: PlanningInputDto;
  definition_fingerprint: string;
  created_at: string;
};

export type WorkflowTemplateRevision = WorkflowExecutionBoundary & {
  id: string;
  workspaceId: string;
  projectId: string;
  workflowTemplateId: string;
  createdByUserId: string;
  revisionNumber: number;
  definition: PlanningInput;
  definitionFingerprint: string;
  createdAt: string;
};

export type WorkflowTemplateDto = WorkflowExecutionBoundaryDto & {
  id: string;
  workspace_id: string;
  project_id: string;
  created_by_user_id: string;
  name: string;
  template_key: string;
  description: string | null;
  status: WorkflowTemplateStatus;
  current_revision_id: string | null;
  current_revision?: WorkflowTemplateRevisionDto | null;
  created_at: string;
  updated_at: string;
};

export type WorkflowTemplate = WorkflowExecutionBoundary & {
  id: string;
  workspaceId: string;
  projectId: string;
  createdByUserId: string;
  name: string;
  templateKey: string;
  description: string | null;
  status: WorkflowTemplateStatus;
  currentRevisionId: string | null;
  currentRevision?: WorkflowTemplateRevision | null;
  createdAt: string;
  updatedAt: string;
};

export type WorkflowTemplateMutationResultDto = WorkflowExecutionBoundaryDto & {
  database_write: boolean;
  idempotent_replay: boolean;
  outcome: "created" | "updated";
  template: WorkflowTemplateDto;
  revision?: WorkflowTemplateRevisionDto | null;
};

export type WorkflowTemplateMutationResult = WorkflowExecutionBoundary & {
  databaseWrite: boolean;
  idempotentReplay: boolean;
  outcome: "created" | "updated";
  template: WorkflowTemplate;
  revision?: WorkflowTemplateRevision | null;
};

export type WorkflowTemplateReadBoundaryDto = WorkflowExecutionBoundaryDto & {
  database_write: false;
};

export type WorkflowTemplateReadBoundary = WorkflowExecutionBoundary & {
  databaseWrite: false;
};

export type WorkflowTemplateListResultDto = WorkflowTemplateReadBoundaryDto & {
  project_status: ProjectStatus;
  items: WorkflowTemplateDto[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowTemplateListResult = WorkflowTemplateReadBoundary & {
  projectStatus: ProjectStatus;
  items: WorkflowTemplate[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowTemplateDetailDto = WorkflowTemplateReadBoundaryDto & {
  project_status: ProjectStatus;
  template: WorkflowTemplateDto;
  current_revision: WorkflowTemplateRevisionDto;
};

export type WorkflowTemplateDetail = WorkflowTemplateReadBoundary & {
  projectStatus: ProjectStatus;
  template: WorkflowTemplate;
  currentRevision: WorkflowTemplateRevision;
};

export type WorkflowTemplateRevisionListResultDto = WorkflowTemplateReadBoundaryDto & {
  project_status: ProjectStatus;
  template: WorkflowTemplateDto;
  items: WorkflowTemplateRevisionDto[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowTemplateRevisionListResult = WorkflowTemplateReadBoundary & {
  projectStatus: ProjectStatus;
  template: WorkflowTemplate;
  items: WorkflowTemplateRevision[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowPlanListResultDto = WorkflowPlanReadBoundaryDto & {
  project_status: ProjectStatus;
  items: WorkflowPlanDto[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowPlanListResult = WorkflowPlanReadBoundary & {
  projectStatus: ProjectStatus;
  items: WorkflowPlan[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowPlanDetailDto = WorkflowPlanReadBoundaryDto & {
  project_status: ProjectStatus;
  plan: WorkflowPlanDto;
  current_version: WorkflowVersionDto;
};

export type WorkflowPlanDetail = WorkflowPlanReadBoundary & {
  projectStatus: ProjectStatus;
  plan: WorkflowPlan;
  currentVersion: WorkflowVersion;
};

export type WorkflowVersionListResultDto = WorkflowPlanReadBoundaryDto & {
  project_status: ProjectStatus;
  items: WorkflowVersionSummaryDto[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowVersionListResult = WorkflowPlanReadBoundary & {
  projectStatus: ProjectStatus;
  items: WorkflowVersionSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowVersionDetailDto = WorkflowPlanReadBoundaryDto & {
  project_status: ProjectStatus;
  plan: WorkflowPlanDto;
  version: WorkflowVersionDto;
};

export type WorkflowVersionDetail = WorkflowPlanReadBoundary & {
  projectStatus: ProjectStatus;
  plan: WorkflowPlan;
  version: WorkflowVersion;
};

export type MonitoringScopeListResultDto = WorkflowPlanReadBoundaryDto & {
  project_status: ProjectStatus;
  items: MonitoringScopeDto[];
  total: number;
  limit: number;
  offset: number;
};

export type MonitoringScopeListResult = WorkflowPlanReadBoundary & {
  projectStatus: ProjectStatus;
  items: MonitoringScope[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkflowPlanCompareChangeDto = {
  field: string;
  before: PlannerJsonValue | null;
  after: PlannerJsonValue | null;
};

export type WorkflowPlanCompareChange = {
  field: string;
  before: PlannerJsonValue | null;
  after: PlannerJsonValue | null;
};

export type WorkflowPlanCompareSectionDto = {
  key: string;
  changes: WorkflowPlanCompareChangeDto[];
};

export type WorkflowPlanCompareSection = {
  key: string;
  changes: WorkflowPlanCompareChange[];
};

export type WorkflowPlanVersionCompareDto = WorkflowPlanReadBoundaryDto & {
  project_status: ProjectStatus;
  plan: WorkflowPlanDto;
  base_version: WorkflowVersionSummaryDto;
  target_version: WorkflowVersionSummaryDto;
  same_version: boolean;
  sections: WorkflowPlanCompareSectionDto[];
};

export type WorkflowPlanVersionCompare = WorkflowPlanReadBoundary & {
  projectStatus: ProjectStatus;
  plan: WorkflowPlan;
  baseVersion: WorkflowVersionSummary;
  targetVersion: WorkflowVersionSummary;
  sameVersion: boolean;
  sections: WorkflowPlanCompareSection[];
};
