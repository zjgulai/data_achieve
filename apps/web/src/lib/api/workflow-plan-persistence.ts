import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import {
  mapPlanningInputToDto,
  mapWorkflowPlanPreview,
} from "@/lib/api/workflow-plans";
import {
  compareWorkflowPlanVersionsMock,
  createWorkflowPlanMock,
  createWorkflowVersionMock,
  getWorkflowPlanMock,
  getWorkflowVersionMock,
  listMonitoringScopesMock,
  listWorkflowPlansMock,
  listWorkflowPlanVersionsMock,
} from "@/lib/workflow-plan-persistence-mock";
import type {
  ApiRequestOptions,
  MonitoringScope,
  MonitoringScopeDto,
  MonitoringScopeListResult,
  MonitoringScopeListResultDto,
  PaginationOptions,
  WorkflowExecutionBoundary,
  WorkflowExecutionBoundaryDto,
  WorkflowPlan,
  WorkflowPlanCreateInput,
  WorkflowPlanCreateRequestDto,
  WorkflowPlanDetail,
  WorkflowPlanDetailDto,
  WorkflowPlanDto,
  WorkflowPlanListResult,
  WorkflowPlanListResultDto,
  WorkflowPlanReadBoundary,
  WorkflowPlanReadBoundaryDto,
  WorkflowPlanSaveResult,
  WorkflowPlanSaveResultDto,
  WorkflowPlanVersionCompare,
  WorkflowPlanVersionCompareDto,
  WorkflowVersion,
  WorkflowVersionCreateInput,
  WorkflowVersionCreateRequestDto,
  WorkflowVersionDetail,
  WorkflowVersionDetailDto,
  WorkflowVersionDto,
  WorkflowVersionListResult,
  WorkflowVersionListResultDto,
  WorkflowVersionSummary,
  WorkflowVersionSummaryDto,
} from "@/types/workflow-plan-persistence";
import type { PlanningInput } from "@/types/workflow-planner";

export async function createWorkflowPlan(
  projectId: string,
  input: WorkflowPlanCreateInput,
  options: ApiRequestOptions = {},
): Promise<WorkflowPlanSaveResult> {
  if (mockApiEnabled) {
    return createWorkflowPlanMock(projectId, input);
  }

  const body: WorkflowPlanCreateRequestDto = {
    name: input.name,
    preview_input: mapPlanningInputToDto(input.previewInput),
    expected_preview_fingerprint: input.expectedPreviewFingerprint,
  };
  const response = await apiFetch<WorkflowPlanSaveResultDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-plans`,
    {
      method: "POST",
      headers: { "Idempotency-Key": input.idempotencyKey },
      body: JSON.stringify(body),
      signal: options.signal,
    },
  );
  return mapWorkflowPlanSaveResult(response);
}

export async function createWorkflowVersion(
  projectId: string,
  planId: string,
  input: WorkflowVersionCreateInput,
  options: ApiRequestOptions = {},
): Promise<WorkflowPlanSaveResult> {
  if (mockApiEnabled) {
    return createWorkflowVersionMock(projectId, planId, input);
  }

  const body: WorkflowVersionCreateRequestDto = {
    preview_input: mapPlanningInputToDto(input.previewInput),
    expected_preview_fingerprint: input.expectedPreviewFingerprint,
    expected_current_version_id: input.expectedCurrentVersionId,
  };
  const response = await apiFetch<WorkflowPlanSaveResultDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/${encodeURIComponent(planId)}/versions`,
    {
      method: "POST",
      headers: { "Idempotency-Key": input.idempotencyKey },
      body: JSON.stringify(body),
      signal: options.signal,
    },
  );
  return mapWorkflowPlanSaveResult(response);
}

export async function listWorkflowPlans(
  projectId: string,
  options: PaginationOptions = {},
): Promise<WorkflowPlanListResult> {
  if (mockApiEnabled) {
    return listWorkflowPlansMock(projectId, options);
  }

  const response = await apiFetch<WorkflowPlanListResultDto>(
    withPagination(
      `/api/projects/${encodeURIComponent(projectId)}/workflow-plans`,
      options,
    ),
    { signal: options.signal },
  );
  return {
    ...mapReadBoundary(response),
    projectStatus: response.project_status,
    items: response.items.map(mapWorkflowPlan),
    total: response.total,
    limit: response.limit,
    offset: response.offset,
  };
}

export async function getWorkflowPlan(
  projectId: string,
  planId: string,
  options: ApiRequestOptions = {},
): Promise<WorkflowPlanDetail> {
  if (mockApiEnabled) {
    return getWorkflowPlanMock(projectId, planId);
  }

  const response = await apiFetch<WorkflowPlanDetailDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/${encodeURIComponent(planId)}`,
    { signal: options.signal },
  );
  return {
    ...mapReadBoundary(response),
    projectStatus: response.project_status,
    plan: mapWorkflowPlan(response.plan),
    currentVersion: mapWorkflowVersion(response.current_version),
  };
}

export async function listWorkflowPlanVersions(
  projectId: string,
  planId: string,
  options: PaginationOptions = {},
): Promise<WorkflowVersionListResult> {
  if (mockApiEnabled) {
    return listWorkflowPlanVersionsMock(projectId, planId, options);
  }

  const response = await apiFetch<WorkflowVersionListResultDto>(
    withPagination(
      `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/${encodeURIComponent(planId)}/versions`,
      options,
    ),
    { signal: options.signal },
  );
  return {
    ...mapReadBoundary(response),
    projectStatus: response.project_status,
    items: response.items.map(mapWorkflowVersionSummary),
    total: response.total,
    limit: response.limit,
    offset: response.offset,
  };
}

export async function getWorkflowVersion(
  projectId: string,
  planId: string,
  versionId: string,
  options: ApiRequestOptions = {},
): Promise<WorkflowVersionDetail> {
  if (mockApiEnabled) {
    return getWorkflowVersionMock(projectId, planId, versionId);
  }

  const response = await apiFetch<WorkflowVersionDetailDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/${encodeURIComponent(planId)}/versions/${encodeURIComponent(versionId)}`,
    { signal: options.signal },
  );
  return {
    ...mapReadBoundary(response),
    projectStatus: response.project_status,
    plan: mapWorkflowPlan(response.plan),
    version: mapWorkflowVersion(response.version),
  };
}

export async function compareWorkflowPlanVersions(
  projectId: string,
  planId: string,
  baseVersionId: string,
  targetVersionId: string,
  options: ApiRequestOptions = {},
): Promise<WorkflowPlanVersionCompare> {
  if (mockApiEnabled) {
    return compareWorkflowPlanVersionsMock(
      projectId,
      planId,
      baseVersionId,
      targetVersionId,
    );
  }

  const query = new URLSearchParams({
    base_version_id: baseVersionId,
    target_version_id: targetVersionId,
  });
  const response = await apiFetch<WorkflowPlanVersionCompareDto>(
    `/api/projects/${encodeURIComponent(projectId)}/workflow-plans/${encodeURIComponent(planId)}/version-compare?${query.toString()}`,
    { signal: options.signal },
  );
  return {
    ...mapReadBoundary(response),
    projectStatus: response.project_status,
    plan: mapWorkflowPlan(response.plan),
    baseVersion: mapWorkflowVersionSummary(response.base_version),
    targetVersion: mapWorkflowVersionSummary(response.target_version),
    sameVersion: response.same_version,
    sections: response.sections.map((section) => ({
      key: section.key,
      changes: section.changes.map((change) => ({
        field: change.field,
        before: change.before,
        after: change.after,
      })),
    })),
  };
}

export async function listMonitoringScopes(
  projectId: string,
  options: PaginationOptions = {},
): Promise<MonitoringScopeListResult> {
  if (mockApiEnabled) {
    return listMonitoringScopesMock(projectId, options);
  }

  const response = await apiFetch<MonitoringScopeListResultDto>(
    withPagination(
      `/api/projects/${encodeURIComponent(projectId)}/monitoring-scopes`,
      options,
    ),
    { signal: options.signal },
  );
  return {
    ...mapReadBoundary(response),
    projectStatus: response.project_status,
    items: response.items.map(mapMonitoringScope),
    total: response.total,
    limit: response.limit,
    offset: response.offset,
  };
}

function withPagination(path: string, options: PaginationOptions): string {
  const query = new URLSearchParams();
  if (options.limit !== undefined) {
    query.set("limit", String(options.limit));
  }
  if (options.offset !== undefined) {
    query.set("offset", String(options.offset));
  }
  const serialized = query.toString();
  return serialized.length > 0 ? `${path}?${serialized}` : path;
}

function mapExecutionBoundary(
  response: WorkflowExecutionBoundaryDto,
): WorkflowExecutionBoundary {
  return {
    providerCall: response.provider_call,
    actorRun: response.actor_run,
    browserRun: response.browser_run,
    llmCall: response.llm_call,
    workflowRunCreated: response.workflow_run_created,
    executionAuthorized: response.execution_authorized,
  };
}

function mapReadBoundary(
  response: WorkflowPlanReadBoundaryDto,
): WorkflowPlanReadBoundary {
  return {
    ...mapExecutionBoundary(response),
    databaseWrite: response.database_write,
    planChanged: response.plan_changed,
  };
}

function mapWorkflowPlan(response: WorkflowPlanDto): WorkflowPlan {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    createdByUserId: response.created_by_user_id,
    name: response.name,
    flowMode: response.flow_mode,
    status: response.status,
    currentVersionId: response.current_version_id,
    currentVersionNumber: response.current_version_number,
    planningStatus: response.planning_status,
    scopeCount: response.scope_count,
    queryTermCount: response.query_term_count,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
  };
}

function mapWorkflowVersionSummary(
  response: WorkflowVersionSummaryDto,
): WorkflowVersionSummary {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    workflowPlanId: response.workflow_plan_id,
    createdByUserId: response.created_by_user_id,
    versionNumber: response.version_number,
    planningStatus: response.planning_status,
    plannerContractVersion: response.planner_contract_version,
    catalogSnapshotId: response.catalog_snapshot_id,
    policyVersion: response.policy_version,
    modeTemplateVersion: response.mode_template_version,
    queryVersions: response.query_versions,
    previewFingerprint: response.preview_fingerprint,
    createdAt: response.created_at,
  };
}

function mapWorkflowVersion(response: WorkflowVersionDto): WorkflowVersion {
  return {
    ...mapWorkflowVersionSummary(response),
    editableInput: mapEditablePlanningInput(response.editable_input),
    preview: mapWorkflowPlanPreview(response.preview),
  };
}

function mapEditablePlanningInput(
  response: WorkflowVersionDto["editable_input"],
): PlanningInput {
  const base = {
    scopes: response.scopes.map((scope) => ({
      scopeRef: scope.scope_ref,
      scopeType: scope.scope_type,
      canonicalTerm: scope.canonical_term,
      aliases: scope.aliases,
      includeTerms: scope.include_terms,
      excludeTerms: scope.exclude_terms,
      officialAccounts: scope.official_accounts,
      seedUrls: scope.seed_urls,
      languages: scope.languages,
      regions: scope.regions,
      platforms: scope.platforms,
      matchMode: scope.match_mode,
    })),
    defaultLanguages: response.default_languages,
    defaultRegions: response.default_regions,
    defaultPlatforms: response.default_platforms,
    deliveryIntent: response.delivery_intent,
    policyProfile: response.policy_profile,
    purpose: response.purpose,
    requiredFields: response.required_fields,
    optionalFields: response.optional_fields,
    budgetCeiling: response.budget_ceiling,
    rateLimitIntent: response.rate_limit_intent
      ? {
          maxRequests: response.rate_limit_intent.max_requests,
          periodSeconds: response.rate_limit_intent.period_seconds,
        }
      : null,
    retentionIntent: response.retention_intent,
    allowPartialDegradation: response.allow_partial_degradation,
  };

  if (response.flow_mode === "periodic_monitoring") {
    return {
      ...base,
      flowMode: response.flow_mode,
      scheduleIntent: response.schedule_intent,
    };
  }

  return {
    ...base,
    flowMode: response.flow_mode,
  };
}

function mapWorkflowPlanSaveResult(
  response: WorkflowPlanSaveResultDto,
): WorkflowPlanSaveResult {
  return {
    ...mapExecutionBoundary(response),
    databaseWrite: response.database_write,
    planChanged: response.plan_changed,
    outcome: response.outcome,
    idempotentReplay: response.idempotent_replay,
    plan: mapWorkflowPlan(response.plan),
    version: mapWorkflowVersion(response.version),
  };
}

function mapMonitoringScope(response: MonitoringScopeDto): MonitoringScope {
  return {
    id: response.id,
    workspaceId: response.workspace_id,
    projectId: response.project_id,
    createdByUserId: response.created_by_user_id,
    scopeKey: response.scope_key,
    scopeType: response.scope_type,
    canonicalTerm: response.canonical_term,
    aliases: response.aliases,
    includeTerms: response.include_terms,
    excludeTerms: response.exclude_terms,
    officialAccounts: response.official_accounts,
    seedUrls: response.seed_urls,
    effectiveLanguages: response.effective_languages,
    effectiveRegions: response.effective_regions,
    effectivePlatforms: response.effective_platforms,
    matchMode: response.match_mode,
    createdAt: response.created_at,
  };
}
