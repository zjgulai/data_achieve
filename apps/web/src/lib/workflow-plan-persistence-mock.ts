import { ApiRequestError, type ApiErrorCode } from "@/lib/api/client";
import { buildMockWorkflowPlanPreview } from "@/lib/workflow-planner-mock";
import type {
  MonitoringScope,
  MonitoringScopeListResult,
  MonitoringScopeTemplate,
  MonitoringScopeTemplateCopyInput,
  MonitoringScopeTemplateCopyResult,
  PaginationOptions,
  WorkflowPlan,
  WorkflowPlanCloneInput,
  WorkflowPlanCloneResult,
  WorkflowPlanCompareChange,
  WorkflowPlanCompareSection,
  WorkflowPlanCreateInput,
  WorkflowPlanDetail,
  WorkflowPlanListResult,
  WorkflowPlanSaveResult,
  WorkflowPlanStatus,
  WorkflowPlanTransitionInput,
  WorkflowPlanTransitionResult,
  WorkflowPlanVersionCompare,
  WorkflowVersion,
  WorkflowVersionCreateInput,
  WorkflowVersionDetail,
  WorkflowVersionListResult,
  WorkflowVersionSummary,
  WorkflowTemplate,
  WorkflowTemplateCreateInput,
  WorkflowTemplateDetail,
  WorkflowTemplateInstantiateInput,
  WorkflowTemplateListResult,
  WorkflowTemplateMetadataUpdateInput,
  WorkflowTemplateMutationResult,
  WorkflowTemplateRevision,
  WorkflowTemplateRevisionCreateInput,
  WorkflowTemplateRevisionListResult,
} from "@/types/workflow-plan-persistence";
import type {
  PlannerJsonValue,
  PlanningInput,
  WorkflowPlanPreview,
} from "@/types/workflow-planner";

export const WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID =
  "00000000-0000-4000-8000-000000000033";

const MOCK_WORKSPACE_ID = "30000000-0000-4000-8000-000000000001";
const MOCK_USER_ID = "30000000-0000-4000-8000-000000000002";
const MOCK_ID_PREFIX = "30000000-0000-4000-8000-";
const MOCK_EPOCH_MS = Date.parse("2026-07-13T00:00:00.000Z");
const E2E_PREVIEW_STALE_SAVE_TERM = "e2e-preview-stale-save";
const E2E_VERSION_CONFLICT_SAVE_TERM = "e2e-version-conflict-save";
const E2E_VERSION_CONFLICT_REMOTE_TERM = "e2e-version-conflict-remote";

const READ_BOUNDARY = {
  databaseWrite: false,
  planChanged: false,
  providerCall: false,
  actorRun: false,
  browserRun: false,
  llmCall: false,
  workflowRunCreated: false,
  executionAuthorized: false,
} as const;

const TEMPLATE_READ_BOUNDARY = {
  databaseWrite: false,
  providerCall: false,
  actorRun: false,
  browserRun: false,
  llmCall: false,
  workflowRunCreated: false,
  executionAuthorized: false,
} as const;

type StoredPlan = {
  plan: WorkflowPlan;
  versions: WorkflowVersion[];
};

type StoredIdempotencyResult = {
  requestHash: string;
  response: WorkflowPlanSaveResult;
};

type StoredCloneIdempotencyResult = {
  requestHash: string;
  response: WorkflowPlanCloneResult;
};

type StoredScopeTemplateIdempotencyResult = {
  requestHash: string;
  response: MonitoringScopeTemplateCopyResult;
};

type StoredTemplate = {
  template: WorkflowTemplate;
  revisions: WorkflowTemplateRevision[];
};

type StoredTemplateMutationResult = {
  requestHash: string;
  response: WorkflowTemplateMutationResult;
};

const plansByProject = new Map<string, Map<string, StoredPlan>>();
const scopesByProject = new Map<string, Map<string, MonitoringScope>>();
const idempotencyResults = new Map<string, StoredIdempotencyResult>();
const cloneIdempotencyResults = new Map<string, StoredCloneIdempotencyResult>();
const scopeTemplateIdempotencyResults = new Map<
  string,
  StoredScopeTemplateIdempotencyResult
>();
const templatesByProject = new Map<string, Map<string, StoredTemplate>>();
const templateIdempotencyResults = new Map<
  string,
  StoredTemplateMutationResult
>();
const previewStaleFixturePlanIds = new Set<string>();
const versionConflictFixturePlanIds = new Set<string>();

let idCounter = 0;
let timestampCounter = 0;
let fixtureSeeded = false;
let fixtureSeedPromise: Promise<void> | null = null;

export async function createWorkflowPlanMock(
  projectId: string,
  input: WorkflowPlanCreateInput,
): Promise<WorkflowPlanSaveResult> {
  await ensureMockReady();
  return createWorkflowPlanInternal(projectId, input);
}

export async function createWorkflowTemplateMock(
  projectId: string,
  input: WorkflowTemplateCreateInput,
): Promise<WorkflowTemplateMutationResult> {
  await ensureMockReady();
  const name = input.name.trim();
  const templateKey = input.templateKey.trim();
  if (name.length < 1 || name.length > 200 || templateKey.length < 1) {
    throw mockError(422, "workflow_template_input_invalid");
  }
  const idempotencyKey = normalizeIdempotencyKey(input.idempotencyKey);
  const scope = `workflow_template.create:${projectId}`;
  const recordKey = await idempotencyRecordKey(scope, idempotencyKey);
  const requestHash = await hashValue({
    projectId,
    name,
    templateKey,
    description: input.description ?? null,
    definition: input.definition,
  });
  const completed = templateIdempotencyResults.get(recordKey);
  if (completed) {
    return replayTemplateMutation(completed, requestHash);
  }
  const templates = getOrCreateProjectTemplates(projectId);
  if (
    [...templates.values()].some(
      (entry) => entry.template.templateKey === templateKey,
    )
  ) {
    throw mockError(409, "workflow_template_key_conflict");
  }
  const timestamp = nextTimestamp();
  const templateId = nextId();
  const revision = await buildTemplateRevision({
    projectId,
    templateId,
    revisionNumber: 1,
    definition: input.definition,
    createdAt: timestamp,
  });
  const template: WorkflowTemplate = {
    ...TEMPLATE_READ_BOUNDARY,
    id: templateId,
    workspaceId: MOCK_WORKSPACE_ID,
    projectId,
    createdByUserId: MOCK_USER_ID,
    name,
    templateKey,
    description: input.description?.trim() || null,
    status: "draft",
    currentRevisionId: revision.id,
    currentRevision: revision,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  const response: WorkflowTemplateMutationResult = clone({
    ...TEMPLATE_READ_BOUNDARY,
    databaseWrite: true,
    idempotentReplay: false,
    outcome: "created",
    template,
    revision,
  });
  templates.set(template.id, { template, revisions: [revision] });
  templateIdempotencyResults.set(recordKey, {
    requestHash,
    response: clone(response),
  });
  return clone(response);
}

export async function updateWorkflowTemplateMetadataMock(
  projectId: string,
  templateId: string,
  input: WorkflowTemplateMetadataUpdateInput,
): Promise<WorkflowTemplateMutationResult> {
  await ensureMockReady();
  const idempotencyKey = normalizeIdempotencyKey(input.idempotencyKey);
  const scope = `workflow_template.metadata:${projectId}:${templateId}`;
  const recordKey = await idempotencyRecordKey(scope, idempotencyKey);
  const requestHash = await hashValue({
    projectId,
    templateId,
    expectedRevisionId: input.expectedRevisionId,
    name: input.name,
    description: input.description,
  });
  const completed = templateIdempotencyResults.get(recordKey);
  if (completed) {
    return replayTemplateMutation(completed, requestHash);
  }
  const stored = getStoredTemplate(projectId, templateId);
  assertTemplateDraft(stored, input.expectedRevisionId);
  const template = {
    ...stored.template,
    name: input.name?.trim() || stored.template.name,
    description:
      input.description === undefined
        ? stored.template.description
        : input.description?.trim() || null,
    updatedAt: nextTimestamp(),
  };
  stored.template = template;
  const response: WorkflowTemplateMutationResult = clone({
    ...TEMPLATE_READ_BOUNDARY,
    databaseWrite: true,
    idempotentReplay: false,
    outcome: "updated",
    template,
    revision: null,
  });
  templateIdempotencyResults.set(recordKey, {
    requestHash,
    response: clone(response),
  });
  return clone(response);
}

export async function appendWorkflowTemplateRevisionMock(
  projectId: string,
  templateId: string,
  input: WorkflowTemplateRevisionCreateInput,
): Promise<WorkflowTemplateMutationResult> {
  await ensureMockReady();
  const idempotencyKey = normalizeIdempotencyKey(input.idempotencyKey);
  const scope = `workflow_template.revision:${projectId}:${templateId}`;
  const recordKey = await idempotencyRecordKey(scope, idempotencyKey);
  const requestHash = await hashValue({
    projectId,
    templateId,
    expectedRevisionId: input.expectedRevisionId,
    definition: input.definition,
  });
  const completed = templateIdempotencyResults.get(recordKey);
  if (completed) {
    return replayTemplateMutation(completed, requestHash);
  }
  const stored = getStoredTemplate(projectId, templateId);
  assertTemplateDraft(stored, input.expectedRevisionId);
  const revision = await buildTemplateRevision({
    projectId,
    templateId,
    revisionNumber: stored.revisions.length + 1,
    definition: input.definition,
    createdAt: nextTimestamp(),
  });
  stored.revisions.push(revision);
  stored.template = {
    ...stored.template,
    currentRevisionId: revision.id,
    currentRevision: revision,
    updatedAt: revision.createdAt,
  };
  const response: WorkflowTemplateMutationResult = clone({
    ...TEMPLATE_READ_BOUNDARY,
    databaseWrite: true,
    idempotentReplay: false,
    outcome: "updated",
    template: stored.template,
    revision,
  });
  templateIdempotencyResults.set(recordKey, {
    requestHash,
    response: clone(response),
  });
  return clone(response);
}

export async function listWorkflowTemplatesMock(
  projectId: string,
  options: PaginationOptions = {},
): Promise<WorkflowTemplateListResult> {
  await ensureMockReady();
  const { limit, offset } = normalizePagination(options);
  const items = [...(templatesByProject.get(projectId)?.values() ?? [])]
    .map((entry) => entry.template)
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
    .slice(offset, offset + limit);
  return clone({
    ...TEMPLATE_READ_BOUNDARY,
    projectStatus: "active",
    items,
    total: templatesByProject.get(projectId)?.size ?? 0,
    limit,
    offset,
  });
}

export async function getWorkflowTemplateMock(
  projectId: string,
  templateId: string,
): Promise<WorkflowTemplateDetail> {
  await ensureMockReady();
  const stored = getStoredTemplate(projectId, templateId);
  const current = stored.revisions.find(
    (revision) => revision.id === stored.template.currentRevisionId,
  );
  if (!current) {
    throw mockError(409, "workflow_template_revision_invalid");
  }
  return clone({
    ...TEMPLATE_READ_BOUNDARY,
    projectStatus: "active",
    template: stored.template,
    currentRevision: current,
  });
}

export async function listWorkflowTemplateRevisionsMock(
  projectId: string,
  templateId: string,
  options: PaginationOptions = {},
): Promise<WorkflowTemplateRevisionListResult> {
  await ensureMockReady();
  const stored = getStoredTemplate(projectId, templateId);
  const { limit, offset } = normalizePagination(options);
  const revisions = [...stored.revisions]
    .sort((left, right) => right.revisionNumber - left.revisionNumber)
    .slice(offset, offset + limit);
  return clone({
    ...TEMPLATE_READ_BOUNDARY,
    projectStatus: "active",
    template: stored.template,
    items: revisions,
    total: stored.revisions.length,
    limit,
    offset,
  });
}

export async function instantiateWorkflowPlanFromTemplateMock(
  projectId: string,
  templateId: string,
  input: WorkflowTemplateInstantiateInput,
): Promise<WorkflowPlanSaveResult> {
  await ensureMockReady();
  const stored = getStoredTemplate(projectId, templateId);
  const revision = stored.revisions.find(
    (candidate) => candidate.id === input.revisionId,
  );
  if (!revision) {
    throw mockError(404, "workflow_template_revision_not_found");
  }
  const created = await createWorkflowPlanInternal(
    projectId,
    {
      name: input.name,
      previewInput: revision.definition,
      expectedPreviewFingerprint: (
        await buildMockWorkflowPlanPreview(projectId, revision.definition)
      ).previewFingerprint,
      idempotencyKey: input.idempotencyKey,
    },
    `workflow_template.instantiate:${projectId}:${templateId}`,
    { revisionId: revision.id },
  );
  const version = {
    ...created.version,
    workflowTemplateId: templateId,
    workflowTemplateRevisionId: revision.id,
  };
  const plan = {
    ...created.plan,
    workflowTemplateId: templateId,
    workflowTemplateRevisionId: revision.id,
  };
  if (!created.idempotentReplay) {
    const planStored = getStoredPlan(projectId, created.plan.id);
    planStored.plan = plan;
    planStored.versions = planStored.versions.map((candidate) =>
      candidate.id === version.id ? version : candidate,
    );
  }
  return clone({ ...created, plan, version });
}

export async function createWorkflowVersionMock(
  projectId: string,
  planId: string,
  input: WorkflowVersionCreateInput,
): Promise<WorkflowPlanSaveResult> {
  await ensureMockReady();
  return createWorkflowVersionInternal(projectId, planId, input);
}

export async function transitionWorkflowPlanStatusMock(
  projectId: string,
  planId: string,
  input: WorkflowPlanTransitionInput,
): Promise<WorkflowPlanTransitionResult> {
  await ensureMockReady();
  const stored = getStoredPlan(projectId, planId);
  const fromStatus = stored.plan.status;
  if (fromStatus !== input.expectedStatus) {
    throw mockError(409, "workflow_plan_status_conflict");
  }
  const allowed: Partial<Record<WorkflowPlanStatus, WorkflowPlanStatus[]>> = {
    draft: ["previewed"],
    previewed: ["approved"],
    approved: ["active"],
    active: ["paused"],
    paused: ["active", "archived"],
  };
  if (
    fromStatus !== input.toStatus &&
    !allowed[fromStatus]?.includes(input.toStatus)
  ) {
    throw mockError(409, "workflow_plan_invalid_transition");
  }
  const changed = fromStatus !== input.toStatus;
  if (changed) {
    stored.plan = {
      ...stored.plan,
      status: input.toStatus,
      updatedAt: nextTimestamp(),
    };
  }
  return clone({
    providerCall: false,
    actorRun: false,
    browserRun: false,
    llmCall: false,
    workflowRunCreated: false,
    executionAuthorized: false,
    databaseWrite: changed,
    planChanged: changed,
    idempotentReplay: false,
    fromStatus,
    toStatus: input.toStatus,
    reason: input.reason?.trim() || null,
    plan: stored.plan,
  });
}

export async function cloneWorkflowPlanMock(
  projectId: string,
  planId: string,
  input: WorkflowPlanCloneInput,
): Promise<WorkflowPlanCloneResult> {
  await ensureMockReady();
  const name = input.name.trim();
  if (name.length < 1 || name.length > 200) {
    throw mockError(422, "workflow_plan_name_invalid");
  }
  const idempotencyKey = normalizeIdempotencyKey(input.idempotencyKey);
  const idempotencyScope = `workflow_plan.clone:${projectId}:${planId}`;
  const recordKey = await idempotencyRecordKey(
    idempotencyScope,
    idempotencyKey,
  );
  const requestHash = await hashValue({
    projectId,
    planId,
    name,
    sourceVersionId: input.sourceVersionId,
  });
  const completed = cloneIdempotencyResults.get(recordKey);
  if (completed) {
    if (completed.requestHash !== requestHash) {
      throw mockError(409, "idempotency_conflict");
    }
    return clone({
      ...completed.response,
      databaseWrite: false,
      planChanged: false,
      idempotentReplay: true,
    });
  }

  const source = getStoredPlan(projectId, planId);
  const sourceVersion = getStoredVersion(source, input.sourceVersionId);
  const timestamp = nextTimestamp();
  const targetPlanId = nextId();
  const targetVersion = clone({
    ...sourceVersion,
    id: nextId(),
    workflowPlanId: targetPlanId,
    versionNumber: 1,
    createdAt: timestamp,
  });
  const targetPlan: WorkflowPlan = {
    ...source.plan,
    id: targetPlanId,
    name,
    sourcePlanId: source.plan.id,
    sourceVersionId: sourceVersion.id,
    currentVersionId: targetVersion.id,
    currentVersionNumber: 1,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  getOrCreateProjectPlans(projectId).set(targetPlanId, {
    plan: targetPlan,
    versions: [targetVersion],
  });
  const response: WorkflowPlanCloneResult = clone({
    ...READ_BOUNDARY,
    databaseWrite: true,
    planChanged: true,
    outcome: "created",
    idempotentReplay: false,
    sourcePlanId: source.plan.id,
    sourceVersionId: sourceVersion.id,
    plan: targetPlan,
    version: targetVersion,
  });
  cloneIdempotencyResults.set(recordKey, {
    requestHash,
    response: clone(response),
  });
  return clone(response);
}

export async function copyMonitoringScopeTemplateMock(
  projectId: string,
  scopeId: string,
  input: MonitoringScopeTemplateCopyInput,
): Promise<MonitoringScopeTemplateCopyResult> {
  await ensureMockReady();
  const idempotencyKey = normalizeIdempotencyKey(input.idempotencyKey);
  const idempotencyScope = `monitoring_scope_template.copy:${projectId}:${scopeId}`;
  const recordKey = await idempotencyRecordKey(
    idempotencyScope,
    idempotencyKey,
  );
  const requestHash = await hashValue({
    projectId,
    scopeId,
    sourceVersionId: input.sourceVersionId,
  });
  const completed = scopeTemplateIdempotencyResults.get(recordKey);
  if (completed) {
    if (completed.requestHash !== requestHash) {
      throw mockError(409, "idempotency_conflict");
    }
    return clone({
      ...completed.response,
      databaseWrite: false,
      idempotentReplay: true,
    });
  }

  const sourceScope = [
    ...(scopesByProject.get(projectId)?.values() ?? []),
  ].find((scope) => scope.id === scopeId);
  if (!sourceScope) {
    throw mockError(404, "monitoring_scope_not_found");
  }
  const sourceEntry = [...(plansByProject.get(projectId)?.values() ?? [])].find(
    (stored) =>
      stored.versions.some((version) => version.id === input.sourceVersionId),
  );
  const sourceVersion = sourceEntry?.versions.find(
    (version) => version.id === input.sourceVersionId,
  );
  if (
    !sourceVersion ||
    !sourceVersion.preview.normalizedInput.scopes.some(
      (scope) => scope.scopeKey === sourceScope.scopeKey,
    )
  ) {
    throw mockError(404, "monitoring_scope_not_found");
  }
  const template: MonitoringScopeTemplate = {
    ...READ_BOUNDARY,
    id: nextId(),
    workspaceId: sourceScope.workspaceId,
    projectId,
    createdByUserId: sourceScope.createdByUserId,
    sourceScopeId: sourceScope.id,
    sourcePlanId: sourceEntry!.plan.id,
    sourceVersionId: sourceVersion.id,
    scopeKey: sourceScope.scopeKey,
    scopeType: sourceScope.scopeType,
    canonicalTerm: sourceScope.canonicalTerm,
    aliases: clone(sourceScope.aliases),
    includeTerms: clone(sourceScope.includeTerms),
    excludeTerms: clone(sourceScope.excludeTerms),
    officialAccounts: clone(sourceScope.officialAccounts),
    seedUrls: clone(sourceScope.seedUrls),
    effectiveLanguages: clone(sourceScope.effectiveLanguages),
    effectiveRegions: clone(sourceScope.effectiveRegions),
    effectivePlatforms: clone(sourceScope.effectivePlatforms),
    matchMode: sourceScope.matchMode,
    createdAt: nextTimestamp(),
  };
  const response: MonitoringScopeTemplateCopyResult = clone({
    ...READ_BOUNDARY,
    databaseWrite: true,
    idempotentReplay: false,
    template,
  });
  scopeTemplateIdempotencyResults.set(recordKey, {
    requestHash,
    response: clone(response),
  });
  return clone(response);
}

export async function listWorkflowPlansMock(
  projectId: string,
  options: PaginationOptions = {},
): Promise<WorkflowPlanListResult> {
  await ensureMockReady();
  const { limit, offset } = normalizePagination(options);
  const items = [...(plansByProject.get(projectId)?.values() ?? [])]
    .map((stored) => stored.plan)
    .sort(comparePlans)
    .slice(offset, offset + limit);
  return clone({
    ...READ_BOUNDARY,
    projectStatus: "active",
    items,
    total: plansByProject.get(projectId)?.size ?? 0,
    limit,
    offset,
  });
}

export async function getWorkflowPlanMock(
  projectId: string,
  planId: string,
): Promise<WorkflowPlanDetail> {
  await ensureMockReady();
  const stored = getStoredPlan(projectId, planId);
  return clone({
    ...READ_BOUNDARY,
    projectStatus: "active",
    plan: stored.plan,
    currentVersion: getCurrentVersion(stored),
  });
}

export async function listWorkflowPlanVersionsMock(
  projectId: string,
  planId: string,
  options: PaginationOptions = {},
): Promise<WorkflowVersionListResult> {
  await ensureMockReady();
  const stored = getStoredPlan(projectId, planId);
  const { limit, offset } = normalizePagination(options);
  const versions = [...stored.versions].sort(
    (left, right) => right.versionNumber - left.versionNumber,
  );
  return clone({
    ...READ_BOUNDARY,
    projectStatus: "active",
    items: versions.slice(offset, offset + limit).map(toVersionSummary),
    total: versions.length,
    limit,
    offset,
  });
}

export async function getWorkflowVersionMock(
  projectId: string,
  planId: string,
  versionId: string,
): Promise<WorkflowVersionDetail> {
  await ensureMockReady();
  const stored = getStoredPlan(projectId, planId);
  const version = getStoredVersion(stored, versionId);
  return clone({
    ...READ_BOUNDARY,
    projectStatus: "active",
    plan: stored.plan,
    version,
  });
}

export async function compareWorkflowPlanVersionsMock(
  projectId: string,
  planId: string,
  baseVersionId: string,
  targetVersionId: string,
): Promise<WorkflowPlanVersionCompare> {
  await ensureMockReady();
  const stored = getStoredPlan(projectId, planId);
  const baseVersion = getStoredVersion(stored, baseVersionId);
  const targetVersion =
    baseVersionId === targetVersionId
      ? baseVersion
      : getStoredVersion(stored, targetVersionId);
  return clone({
    ...READ_BOUNDARY,
    projectStatus: "active",
    plan: stored.plan,
    baseVersion: toVersionSummary(baseVersion),
    targetVersion: toVersionSummary(targetVersion),
    sameVersion: baseVersion.id === targetVersion.id,
    sections:
      baseVersion.id === targetVersion.id
        ? []
        : comparePreviews(baseVersion.preview, targetVersion.preview),
  });
}

export async function listMonitoringScopesMock(
  projectId: string,
  options: PaginationOptions = {},
): Promise<MonitoringScopeListResult> {
  await ensureMockReady();
  const { limit, offset } = normalizePagination(options);
  const scopes = [...(scopesByProject.get(projectId)?.values() ?? [])].sort(
    compareScopes,
  );
  return clone({
    ...READ_BOUNDARY,
    projectStatus: "active",
    items: scopes.slice(offset, offset + limit),
    total: scopes.length,
    limit,
    offset,
  });
}

export function resetWorkflowPlanPersistenceMockForTests(): void {
  assertTestHelperUsage();
  plansByProject.clear();
  scopesByProject.clear();
  idempotencyResults.clear();
  cloneIdempotencyResults.clear();
  scopeTemplateIdempotencyResults.clear();
  templatesByProject.clear();
  templateIdempotencyResults.clear();
  previewStaleFixturePlanIds.clear();
  versionConflictFixturePlanIds.clear();
  idCounter = 0;
  timestampCounter = 0;
  fixtureSeeded = false;
  fixtureSeedPromise = null;
}

export async function seedWorkflowPlanPersistenceMockForTests(): Promise<void> {
  assertTestHelperUsage();
  assertMockEnabled();
  if (!fixtureModeEnabled()) {
    throw mockError(503, "workflow_plan_fixture_disabled");
  }
  await seedFixtureOnce();
}

async function ensureMockReady(): Promise<void> {
  assertMockEnabled();
  if (fixtureModeEnabled()) {
    await seedFixtureOnce();
  }
}

function assertMockEnabled(): void {
  if (process.env.NEXT_PUBLIC_MOCK_API !== "true") {
    throw mockError(503, "mock_api_disabled");
  }
}

function fixtureModeEnabled(): boolean {
  return process.env.NEXT_PUBLIC_WORKFLOW_PLANNER_TEST_FIXTURES === "true";
}

async function seedFixtureOnce(): Promise<void> {
  if (fixtureSeeded) {
    return;
  }
  fixtureSeedPromise ??= seedFixture();
  try {
    await fixtureSeedPromise;
  } finally {
    fixtureSeedPromise = null;
  }
}

async function seedFixture(): Promise<void> {
  if (fixtureSeeded) {
    return;
  }
  const firstInput = fixturePlanningInput("fixture baseline");
  const firstPreview = await buildMockWorkflowPlanPreview(
    WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
    firstInput,
  );
  const first = await createWorkflowPlanInternal(
    WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
    {
      name: "Fixture competitor monitoring",
      previewInput: firstInput,
      expectedPreviewFingerprint: firstPreview.previewFingerprint,
      idempotencyKey: "fixture-create-key-0001",
    },
  );
  const secondInput = fixturePlanningInput("fixture current");
  const secondPreview = await buildMockWorkflowPlanPreview(
    WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
    secondInput,
  );
  await createWorkflowVersionInternal(
    WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID,
    first.plan.id,
    {
      previewInput: secondInput,
      expectedPreviewFingerprint: secondPreview.previewFingerprint,
      expectedCurrentVersionId: first.version.id,
      idempotencyKey: "fixture-version-key-0002",
    },
  );
  fixtureSeeded = true;
}

async function createWorkflowPlanInternal(
  projectId: string,
  input: WorkflowPlanCreateInput,
  idempotencyScope = `workflow_plan.create:${projectId}`,
  idempotencyRequestContext: unknown = null,
): Promise<WorkflowPlanSaveResult> {
  const name = input.name.trim();
  if (name.length < 1 || name.length > 200) {
    throw mockError(422, "workflow_plan_name_invalid");
  }
  const idempotencyKey = normalizeIdempotencyKey(input.idempotencyKey);
  const recordKey = await idempotencyRecordKey(
    idempotencyScope,
    idempotencyKey,
  );
  const requestHash = await hashValue({
    projectId,
    name,
    previewInput: input.previewInput,
    expectedPreviewFingerprint: input.expectedPreviewFingerprint,
    idempotencyRequestContext,
  });
  const completed = idempotencyResults.get(recordKey);
  if (completed) {
    return replayOrConflict(completed, requestHash);
  }

  const preview = await buildMockWorkflowPlanPreview(
    projectId,
    input.previewInput,
  );
  assertPreviewCurrent(preview, input.expectedPreviewFingerprint);
  const timestamp = nextTimestamp();
  const planId = nextId();
  const version = buildVersion({
    id: nextId(),
    projectId,
    planId,
    versionNumber: 1,
    previewInput: input.previewInput,
    preview,
    createdAt: timestamp,
  });
  const plan: WorkflowPlan = {
    id: planId,
    workspaceId: MOCK_WORKSPACE_ID,
    projectId,
    createdByUserId: MOCK_USER_ID,
    name,
    flowMode: preview.flowMode,
    status: "previewed",
    currentVersionId: version.id,
    sourcePlanId: null,
    sourceVersionId: null,
    workflowTemplateId: null,
    workflowTemplateRevisionId: null,
    currentVersionNumber: version.versionNumber,
    planningStatus: version.planningStatus,
    scopeCount: preview.normalizedInput.scopes.length,
    queryTermCount: preview.queryTerms.length,
    createdAt: timestamp,
    updatedAt: timestamp,
  };
  const projectPlans = getOrCreateProjectPlans(projectId);
  projectPlans.set(plan.id, { plan, versions: [version] });
  persistMonitoringScopes(projectId, preview, timestamp);

  const response = buildSaveResult({
    plan,
    version,
    outcome: "created",
    planChanged: true,
  });
  saveIdempotencyResult(recordKey, requestHash, response);
  return clone(response);
}

async function createWorkflowVersionInternal(
  projectId: string,
  planId: string,
  input: WorkflowVersionCreateInput,
): Promise<WorkflowPlanSaveResult> {
  const idempotencyKey = normalizeIdempotencyKey(input.idempotencyKey);
  const idempotencyScope = `workflow_plan.create_version:${projectId}:${planId}`;
  const recordKey = await idempotencyRecordKey(
    idempotencyScope,
    idempotencyKey,
  );
  const requestHash = await hashValue({
    projectId,
    planId,
    previewInput: input.previewInput,
    expectedPreviewFingerprint: input.expectedPreviewFingerprint,
    expectedCurrentVersionId: input.expectedCurrentVersionId,
  });
  const completed = idempotencyResults.get(recordKey);
  if (completed) {
    return replayOrConflict(completed, requestHash);
  }

  const stored = getStoredPlan(projectId, planId);
  const preview = await buildMockWorkflowPlanPreview(
    projectId,
    input.previewInput,
  );
  assertPreviewCurrent(preview, input.expectedPreviewFingerprint);
  if (
    saveFixtureTriggered(
      projectId,
      input.previewInput,
      E2E_PREVIEW_STALE_SAVE_TERM,
    ) &&
    !previewStaleFixturePlanIds.has(planId)
  ) {
    previewStaleFixturePlanIds.add(planId);
    throw mockError(409, "preview_stale");
  }
  if (stored.plan.flowMode !== preview.flowMode) {
    throw mockError(409, "workflow_plan_flow_mode_conflict");
  }
  if (stored.plan.currentVersionId !== input.expectedCurrentVersionId) {
    throw mockError(409, "version_conflict", {
      currentVersionId: stored.plan.currentVersionId,
    });
  }
  if (
    saveFixtureTriggered(
      projectId,
      input.previewInput,
      E2E_VERSION_CONFLICT_SAVE_TERM,
    ) &&
    !versionConflictFixturePlanIds.has(planId)
  ) {
    await injectVersionConflictFixture(projectId, planId, input.previewInput);
    throw mockError(409, "version_conflict", {
      currentVersionId: stored.plan.currentVersionId,
    });
  }
  const currentVersion = getCurrentVersion(stored);
  if (currentVersion.previewFingerprint === preview.previewFingerprint) {
    const response = buildSaveResult({
      plan: stored.plan,
      version: currentVersion,
      outcome: "semantic_no_op",
      planChanged: false,
    });
    saveIdempotencyResult(recordKey, requestHash, response);
    return clone(response);
  }

  const timestamp = nextTimestamp();
  const version = buildVersion({
    id: nextId(),
    projectId,
    planId,
    versionNumber: currentVersion.versionNumber + 1,
    previewInput: input.previewInput,
    preview,
    createdAt: timestamp,
    workflowTemplateId: stored.plan.workflowTemplateId,
    workflowTemplateRevisionId: stored.plan.workflowTemplateRevisionId,
  });
  stored.versions.push(version);
  stored.plan = {
    ...stored.plan,
    currentVersionId: version.id,
    currentVersionNumber: version.versionNumber,
    planningStatus: version.planningStatus,
    scopeCount: preview.normalizedInput.scopes.length,
    queryTermCount: preview.queryTerms.length,
    updatedAt: timestamp,
  };
  persistMonitoringScopes(projectId, preview, timestamp);

  const response = buildSaveResult({
    plan: stored.plan,
    version,
    outcome: "created",
    planChanged: true,
  });
  saveIdempotencyResult(recordKey, requestHash, response);
  return clone(response);
}

function buildVersion({
  id,
  projectId,
  planId,
  versionNumber,
  previewInput,
  preview,
  createdAt,
  workflowTemplateId,
  workflowTemplateRevisionId,
}: {
  id: string;
  projectId: string;
  planId: string;
  versionNumber: number;
  previewInput: PlanningInput;
  preview: WorkflowPlanPreview;
  createdAt: string;
  workflowTemplateId?: string | null;
  workflowTemplateRevisionId?: string | null;
}): WorkflowVersion {
  return {
    id,
    workspaceId: MOCK_WORKSPACE_ID,
    projectId,
    workflowPlanId: planId,
    workflowTemplateId: workflowTemplateId ?? null,
    workflowTemplateRevisionId: workflowTemplateRevisionId ?? null,
    createdByUserId: MOCK_USER_ID,
    versionNumber,
    planningStatus: preview.planningStatus,
    plannerContractVersion: preview.plannerContractVersion,
    catalogSnapshotId: preview.catalogSnapshotId,
    policyVersion: preview.policyVersion,
    modeTemplateVersion: preview.modeTemplateVersion,
    queryVersions: clone(preview.queryVersions),
    previewFingerprint: preview.previewFingerprint,
    createdAt,
    editableInput: buildCanonicalEditableInput(previewInput, preview),
    preview: clone(preview),
  };
}

function buildCanonicalEditableInput(
  source: PlanningInput,
  preview: WorkflowPlanPreview,
): PlanningInput {
  const defaultLanguages = canonicalEditableStrings(source.defaultLanguages);
  const defaultRegions = canonicalEditableStrings(source.defaultRegions);
  const defaultPlatforms = canonicalEditablePlatforms(source.defaultPlatforms);
  const base = {
    scopes: preview.normalizedInput.scopes.map((scope, index) => ({
      scopeRef: `scope-${index + 1}`,
      scopeType: scope.scopeType,
      canonicalTerm: scope.canonicalTerm,
      aliases: clone(scope.aliases),
      includeTerms: clone(scope.includeTerms),
      excludeTerms: clone(scope.excludeTerms),
      officialAccounts: clone(scope.officialAccounts),
      seedUrls: clone(scope.seedUrls),
      languages: editableScopeOverride(
        scope.effectiveLanguages,
        defaultLanguages,
      ),
      regions: editableScopeOverride(scope.effectiveRegions, defaultRegions),
      platforms: editableScopeOverride(
        scope.effectivePlatforms,
        defaultPlatforms,
      ),
      matchMode: scope.matchMode,
    })),
    defaultLanguages,
    defaultRegions,
    defaultPlatforms,
    deliveryIntent: preview.normalizedInput.deliveryIntent
      ? clone(preview.normalizedInput.deliveryIntent)
      : null,
    policyProfile: preview.normalizedInput.policyProfile,
    purpose: preview.normalizedInput.purpose,
    requiredFields: clone(preview.normalizedInput.requiredFields),
    optionalFields: clone(preview.normalizedInput.optionalFields),
    budgetCeiling: preview.normalizedInput.budgetCeiling
      ? clone(preview.normalizedInput.budgetCeiling)
      : null,
    rateLimitIntent: preview.normalizedInput.rateLimitIntent
      ? clone(preview.normalizedInput.rateLimitIntent)
      : null,
    retentionIntent: preview.normalizedInput.retentionIntent
      ? clone(preview.normalizedInput.retentionIntent)
      : null,
    allowPartialDegradation: preview.normalizedInput.allowPartialDegradation,
  };

  if (preview.flowMode === "periodic_monitoring") {
    const scheduleIntent = preview.normalizedInput.scheduleIntent;
    if (!scheduleIntent) {
      throw new Error("workflow_plan_mock_periodic_schedule_missing");
    }
    return clone({
      ...base,
      flowMode: preview.flowMode,
      scheduleIntent: {
        cadence: scheduleIntent.cadence,
        timezone: canonicalEditableText(scheduleIntent.timezone),
      },
    });
  }

  return clone({
    ...base,
    flowMode: preview.flowMode,
  });
}

function canonicalEditableStrings(values: string[]): string[] {
  return [...new Set(values.map(canonicalEditableText).filter(Boolean))].sort(
    compareStrings,
  );
}

function canonicalEditablePlatforms(
  values: PlanningInput["defaultPlatforms"],
): PlanningInput["defaultPlatforms"] {
  return [...new Set(values)].sort(compareStrings);
}

function canonicalEditableText(value: string): string {
  return value.normalize("NFKC").trim().toLowerCase();
}

function editableScopeOverride<T extends string>(
  effective: T[],
  defaults: T[],
): T[] {
  return arraysEqual(effective, defaults) ? [] : clone(effective);
}

function arraysEqual<T>(left: T[], right: T[]): boolean {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  );
}

function buildSaveResult({
  plan,
  version,
  outcome,
  planChanged,
}: {
  plan: WorkflowPlan;
  version: WorkflowVersion;
  outcome: "created" | "semantic_no_op";
  planChanged: boolean;
}): WorkflowPlanSaveResult {
  return clone({
    databaseWrite: true,
    planChanged,
    outcome,
    idempotentReplay: false,
    providerCall: false,
    actorRun: false,
    browserRun: false,
    llmCall: false,
    workflowRunCreated: false,
    executionAuthorized: false,
    plan,
    version,
  });
}

function replayOrConflict(
  stored: StoredIdempotencyResult,
  requestHash: string,
): WorkflowPlanSaveResult {
  if (stored.requestHash !== requestHash) {
    throw mockError(409, "idempotency_conflict");
  }
  return clone({
    ...stored.response,
    databaseWrite: false,
    planChanged: false,
    idempotentReplay: true,
  });
}

function saveIdempotencyResult(
  recordKey: string,
  requestHash: string,
  response: WorkflowPlanSaveResult,
): void {
  idempotencyResults.set(recordKey, {
    requestHash,
    response: clone(response),
  });
}

function persistMonitoringScopes(
  projectId: string,
  preview: WorkflowPlanPreview,
  createdAt: string,
): void {
  let projectScopes = scopesByProject.get(projectId);
  if (!projectScopes) {
    projectScopes = new Map();
    scopesByProject.set(projectId, projectScopes);
  }
  for (const scope of preview.normalizedInput.scopes) {
    if (projectScopes.has(scope.scopeKey)) {
      continue;
    }
    projectScopes.set(scope.scopeKey, {
      id: nextId(),
      workspaceId: MOCK_WORKSPACE_ID,
      projectId,
      createdByUserId: MOCK_USER_ID,
      scopeKey: scope.scopeKey,
      scopeType: scope.scopeType,
      canonicalTerm: scope.canonicalTerm,
      aliases: clone(scope.aliases),
      includeTerms: clone(scope.includeTerms),
      excludeTerms: clone(scope.excludeTerms),
      officialAccounts: clone(scope.officialAccounts),
      seedUrls: clone(scope.seedUrls),
      effectiveLanguages: clone(scope.effectiveLanguages),
      effectiveRegions: clone(scope.effectiveRegions),
      effectivePlatforms: clone(scope.effectivePlatforms),
      matchMode: scope.matchMode,
      createdAt,
    });
  }
}

function getOrCreateProjectPlans(projectId: string): Map<string, StoredPlan> {
  let plans = plansByProject.get(projectId);
  if (!plans) {
    plans = new Map();
    plansByProject.set(projectId, plans);
  }
  return plans;
}

function getOrCreateProjectTemplates(
  projectId: string,
): Map<string, StoredTemplate> {
  let templates = templatesByProject.get(projectId);
  if (!templates) {
    templates = new Map();
    templatesByProject.set(projectId, templates);
  }
  return templates;
}

function getStoredTemplate(
  projectId: string,
  templateId: string,
): StoredTemplate {
  const stored = templatesByProject.get(projectId)?.get(templateId);
  if (!stored) {
    throw mockError(404, "workflow_template_not_found");
  }
  return stored;
}

function assertTemplateDraft(
  stored: StoredTemplate,
  expectedRevisionId: string,
): void {
  if (stored.template.status !== "draft") {
    throw mockError(409, "workflow_template_not_editable");
  }
  if (stored.template.currentRevisionId !== expectedRevisionId) {
    throw mockError(409, "workflow_template_revision_conflict");
  }
}

async function buildTemplateRevision({
  projectId,
  templateId,
  revisionNumber,
  definition,
  createdAt,
}: {
  projectId: string;
  templateId: string;
  revisionNumber: number;
  definition: PlanningInput;
  createdAt: string;
}): Promise<WorkflowTemplateRevision> {
  return {
    ...TEMPLATE_READ_BOUNDARY,
    id: nextId(),
    workspaceId: MOCK_WORKSPACE_ID,
    projectId,
    workflowTemplateId: templateId,
    createdByUserId: MOCK_USER_ID,
    revisionNumber,
    definition: clone(definition),
    definitionFingerprint: `sha256:${await hashValue(definition)}`,
    createdAt,
  };
}

function replayTemplateMutation(
  stored: StoredTemplateMutationResult,
  requestHash: string,
): WorkflowTemplateMutationResult {
  if (stored.requestHash !== requestHash) {
    throw mockError(409, "idempotency_conflict");
  }
  return clone({
    ...stored.response,
    databaseWrite: false,
    idempotentReplay: true,
  });
}

function getStoredPlan(projectId: string, planId: string): StoredPlan {
  const stored = plansByProject.get(projectId)?.get(planId);
  if (!stored) {
    throw mockError(404, "workflow_plan_not_found");
  }
  return stored;
}

function getStoredVersion(
  stored: StoredPlan,
  versionId: string,
): WorkflowVersion {
  const version = stored.versions.find(
    (candidate) => candidate.id === versionId,
  );
  if (!version) {
    throw mockError(404, "workflow_version_not_found");
  }
  return version;
}

function getCurrentVersion(stored: StoredPlan): WorkflowVersion {
  return getStoredVersion(stored, stored.plan.currentVersionId);
}

function toVersionSummary(version: WorkflowVersion): WorkflowVersionSummary {
  return {
    id: version.id,
    workspaceId: version.workspaceId,
    projectId: version.projectId,
    workflowPlanId: version.workflowPlanId,
    workflowTemplateId: version.workflowTemplateId,
    workflowTemplateRevisionId: version.workflowTemplateRevisionId,
    createdByUserId: version.createdByUserId,
    versionNumber: version.versionNumber,
    planningStatus: version.planningStatus,
    plannerContractVersion: version.plannerContractVersion,
    catalogSnapshotId: version.catalogSnapshotId,
    policyVersion: version.policyVersion,
    modeTemplateVersion: version.modeTemplateVersion,
    queryVersions: clone(version.queryVersions),
    previewFingerprint: version.previewFingerprint,
    createdAt: version.createdAt,
  };
}

function assertPreviewCurrent(
  preview: WorkflowPlanPreview,
  expectedFingerprint: string,
): void {
  if (preview.previewFingerprint !== expectedFingerprint) {
    throw mockError(409, "preview_stale");
  }
}

function normalizeIdempotencyKey(value: string): string {
  const normalized = value.trim();
  if (normalized.length < 12 || normalized.length > 200) {
    throw mockError(422, "idempotency_key_invalid");
  }
  return normalized;
}

function normalizePagination(options: PaginationOptions): {
  limit: number;
  offset: number;
} {
  const limit = options.limit ?? 50;
  const offset = options.offset ?? 0;
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
    throw mockError(422, "pagination_invalid");
  }
  if (!Number.isInteger(offset) || offset < 0) {
    throw mockError(422, "pagination_invalid");
  }
  return { limit, offset };
}

function comparePlans(left: WorkflowPlan, right: WorkflowPlan): number {
  return (
    right.updatedAt.localeCompare(left.updatedAt) ||
    right.id.localeCompare(left.id)
  );
}

function compareScopes(left: MonitoringScope, right: MonitoringScope): number {
  return (
    right.createdAt.localeCompare(left.createdAt) ||
    right.id.localeCompare(left.id)
  );
}

function nextId(): string {
  idCounter += 1;
  return `${MOCK_ID_PREFIX}${idCounter.toString(16).padStart(12, "0")}`;
}

function nextTimestamp(): string {
  timestampCounter += 1;
  return new Date(MOCK_EPOCH_MS + timestampCounter * 1_000).toISOString();
}

async function idempotencyRecordKey(
  scope: string,
  key: string,
): Promise<string> {
  return `${scope}:${await sha256(key)}`;
}

async function hashValue(value: unknown): Promise<string> {
  return sha256(stableJson(value));
}

async function sha256(value: string): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function stableJson(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value ?? null);
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableJson).join(",")}]`;
  }
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record)
    .filter((key) => record[key] !== undefined)
    .sort(compareStrings)
    .map((key) => `${JSON.stringify(key)}:${stableJson(record[key])}`)
    .join(",")}}`;
}

function comparePreviews(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection[] {
  const sections = [
    comparePlanSection(base, target),
    compareScopeSection(base, target),
    compareQueryTermSection(base, target),
    compareVersionSection(base, target),
    compareWarningsSection(base, target),
    compareBlockingIssuesSection(base, target),
    compareRoutesSection(base, target),
    compareBudgetSection(base, target),
    compareLimitsSection(base, target),
    compareStepsSection(base, target),
  ];
  return sections.filter(
    (section): section is WorkflowPlanCompareSection => section !== null,
  );
}

function comparePlanSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  const fields: Array<[string, unknown, unknown]> = [
    ["schema_version", base.schemaVersion, target.schemaVersion],
    ["flow_mode", base.flowMode, target.flowMode],
    ["planning_status", base.planningStatus, target.planningStatus],
    ["purpose", base.normalizedInput.purpose, target.normalizedInput.purpose],
    [
      "policy_profile",
      base.normalizedInput.policyProfile,
      target.normalizedInput.policyProfile,
    ],
    [
      "schedule_intent",
      base.normalizedInput.scheduleIntent,
      target.normalizedInput.scheduleIntent,
    ],
    [
      "delivery_intent",
      base.normalizedInput.deliveryIntent,
      target.normalizedInput.deliveryIntent,
    ],
    [
      "required_fields",
      base.normalizedInput.requiredFields,
      target.normalizedInput.requiredFields,
    ],
    [
      "optional_fields",
      base.normalizedInput.optionalFields,
      target.normalizedInput.optionalFields,
    ],
    [
      "allow_partial_degradation",
      base.normalizedInput.allowPartialDegradation,
      target.normalizedInput.allowPartialDegradation,
    ],
    ["coverage", base.coverage, target.coverage],
    [
      "attribution_contract",
      base.attributionContract,
      target.attributionContract,
    ],
  ];
  for (const [field, before, after] of fields) {
    appendChange(changes, field, before, after);
  }
  return section("plan", changes);
}

function compareScopeSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  const baseByKey = new Map(
    base.normalizedInput.scopes.map((scope) => [
      scope.scopeKey,
      scopePayload(scope),
    ]),
  );
  const targetByKey = new Map(
    target.normalizedInput.scopes.map((scope) => [
      scope.scopeKey,
      scopePayload(scope),
    ]),
  );
  const baseKeys = new Set(baseByKey.keys());
  const targetKeys = new Set(targetByKey.keys());
  const added = [...targetKeys]
    .filter((key) => !baseKeys.has(key))
    .sort(compareStrings);
  const removed = [...baseKeys]
    .filter((key) => !targetKeys.has(key))
    .sort(compareStrings);
  if (added.length > 0) {
    appendChange(
      changes,
      "added",
      [],
      added.map((key) => targetByKey.get(key)),
    );
  }
  if (removed.length > 0) {
    appendChange(
      changes,
      "removed",
      removed.map((key) => baseByKey.get(key)),
      [],
    );
  }
  const common = new Set([...baseKeys].filter((key) => targetKeys.has(key)));
  appendOrderedChange(
    changes,
    "order",
    base.normalizedInput.scopes
      .filter((scope) => common.has(scope.scopeKey))
      .map((scope) => scope.scopeKey),
    target.normalizedInput.scopes
      .filter((scope) => common.has(scope.scopeKey))
      .map((scope) => scope.scopeKey),
  );
  const changed = [...common]
    .sort(compareStrings)
    .filter(
      (key) =>
        canonicalJson(baseByKey.get(key)) !==
        canonicalJson(targetByKey.get(key)),
    );
  if (changed.length > 0) {
    appendChange(
      changes,
      "changed",
      changed.map((key) => baseByKey.get(key)),
      changed.map((key) => targetByKey.get(key)),
    );
  }
  return section("scopes", changes);
}

function compareQueryTermSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  const baseByKey = new Map(
    base.queryTerms.map((term) => [
      canonicalJson(queryTermIdentity(term)),
      term,
    ]),
  );
  const targetByKey = new Map(
    target.queryTerms.map((term) => [
      canonicalJson(queryTermIdentity(term)),
      term,
    ]),
  );
  const baseKeys = new Set(baseByKey.keys());
  const targetKeys = new Set(targetByKey.keys());
  const added = [...targetKeys]
    .filter((key) => !baseKeys.has(key))
    .sort(compareStrings);
  const removed = [...baseKeys]
    .filter((key) => !targetKeys.has(key))
    .sort(compareStrings);
  if (added.length > 0) {
    appendChange(
      changes,
      "added",
      [],
      added.map((key) => queryTermPayload(targetByKey.get(key)!)),
    );
  }
  if (removed.length > 0) {
    appendChange(
      changes,
      "removed",
      removed.map((key) => queryTermPayload(baseByKey.get(key)!)),
      [],
    );
  }
  const common = [...baseKeys]
    .filter((key) => targetKeys.has(key))
    .sort(compareStrings);
  const statusChanged = common.filter(
    (key) => baseByKey.get(key)!.status !== targetByKey.get(key)!.status,
  );
  if (statusChanged.length > 0) {
    appendChange(
      changes,
      "status_changed",
      statusChanged.map((key) => ({
        ...queryTermIdentity(baseByKey.get(key)!),
        status: baseByKey.get(key)!.status,
      })),
      statusChanged.map((key) => ({
        ...queryTermIdentity(targetByKey.get(key)!),
        status: targetByKey.get(key)!.status,
      })),
    );
  }
  const changed = common.filter((key) => {
    const basePayload = queryTermPayload(baseByKey.get(key)!);
    const targetPayload = queryTermPayload(targetByKey.get(key)!);
    delete basePayload.status;
    delete targetPayload.status;
    return canonicalJson(basePayload) !== canonicalJson(targetPayload);
  });
  if (changed.length > 0) {
    appendChange(
      changes,
      "changed",
      changed.map((key) => queryTermPayload(baseByKey.get(key)!)),
      changed.map((key) => queryTermPayload(targetByKey.get(key)!)),
    );
  }
  appendChange(
    changes,
    "compiled_queries",
    base.compiledQueries.map(compiledQueryPayload),
    target.compiledQueries.map(compiledQueryPayload),
  );
  return section("query_terms", changes);
}

function compareVersionSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  const fields: Array<[string, unknown, unknown]> = [
    [
      "planner_contract_version",
      base.plannerContractVersion,
      target.plannerContractVersion,
    ],
    ["catalog_snapshot_id", base.catalogSnapshotId, target.catalogSnapshotId],
    ["policy_version", base.policyVersion, target.policyVersion],
    [
      "mode_template_version",
      base.modeTemplateVersion,
      target.modeTemplateVersion,
    ],
    ["query_versions", base.queryVersions, target.queryVersions],
  ];
  for (const [field, before, after] of fields) {
    appendChange(changes, field, before, after);
  }
  return section("versions", changes);
}

function compareWarningsSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  appendChange(
    changes,
    "input_diagnostics",
    base.decisionTrace.inputDiagnostics,
    target.decisionTrace.inputDiagnostics,
  );
  return section("warnings", changes);
}

function compareBlockingIssuesSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  appendChange(changes, "items", blockingIssues(base), blockingIssues(target));
  return section("blocking_issues", changes);
}

function compareRoutesSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  appendChange(
    changes,
    "route_requirements",
    base.routeRequirements,
    target.routeRequirements,
  );
  appendChange(changes, "route_plans", base.routePlans, target.routePlans);
  return section("routes", changes);
}

function compareBudgetSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  appendChange(
    changes,
    "budget_ceiling",
    base.normalizedInput.budgetCeiling,
    target.normalizedInput.budgetCeiling,
  );
  appendChange(
    changes,
    "budget_summary",
    base.budgetSummary,
    target.budgetSummary,
  );
  return section("budget", changes);
}

function compareLimitsSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  appendChange(
    changes,
    "rate_limit_intent",
    base.normalizedInput.rateLimitIntent,
    target.normalizedInput.rateLimitIntent,
  );
  appendChange(
    changes,
    "retention_intent",
    base.normalizedInput.retentionIntent,
    target.normalizedInput.retentionIntent,
  );
  appendChange(changes, "limitations", base.limitations, target.limitations);
  return section("limits", changes);
}

function compareStepsSection(
  base: WorkflowPlanPreview,
  target: WorkflowPlanPreview,
): WorkflowPlanCompareSection | null {
  const changes: WorkflowPlanCompareChange[] = [];
  appendChange(changes, "items", base.steps, target.steps);
  return section("steps", changes);
}

function scopePayload(
  scope: WorkflowPlanPreview["normalizedInput"]["scopes"][number],
) {
  const payload = { ...scope } as Record<string, unknown>;
  delete payload.sourceScopeRefs;
  return payload;
}

function queryTermIdentity(term: WorkflowPlanPreview["queryTerms"][number]) {
  return {
    normalizedTerm: term.normalizedTerm,
    origin: term.origin,
    scopeKey: term.scopeKey,
    source: term.source,
    term: term.term,
  };
}

function queryTermPayload(
  term: WorkflowPlanPreview["queryTerms"][number],
): Record<string, unknown> {
  const payload = { ...term } as Record<string, unknown>;
  delete payload.scopeRef;
  return payload;
}

function compiledQueryPayload(
  query: WorkflowPlanPreview["compiledQueries"][number],
): Record<string, unknown> {
  const payload = { ...query } as Record<string, unknown>;
  delete payload.sourceScopeRefs;
  return payload;
}

function blockingIssues(preview: WorkflowPlanPreview): PlannerJsonValue[] {
  return preview.routePlans
    .filter((route) => route.status !== "resolved" || route.approvalRequired)
    .map((route) =>
      canonicalize({
        approvalReasons: route.approvalReasons,
        approvalRequired: route.approvalRequired,
        degradationRule: route.degradationRule,
        exclusionReasons: route.exclusionReasons,
        policyGates: route.policyGates,
        requirementRef: route.requirementRef,
        status: route.status,
      }),
    )
    .sort((left, right) =>
      canonicalJson(left).localeCompare(canonicalJson(right)),
    );
}

function appendChange(
  changes: WorkflowPlanCompareChange[],
  field: string,
  before: unknown,
  after: unknown,
): void {
  const canonicalBefore = canonicalize(toSnakeCaseJson(before));
  const canonicalAfter = canonicalize(toSnakeCaseJson(after));
  if (canonicalJson(canonicalBefore) !== canonicalJson(canonicalAfter)) {
    changes.push({ field, before: canonicalBefore, after: canonicalAfter });
  }
}

function toSnakeCaseJson(value: unknown): PlannerJsonValue {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (value === undefined) {
    return null;
  }
  if (Array.isArray(value)) {
    return value.map(toSnakeCaseJson);
  }
  if (typeof value === "object") {
    const source = value as Record<string, unknown>;
    const result: Record<string, PlannerJsonValue> = {};
    for (const key of Object.keys(source)) {
      if (source[key] !== undefined) {
        result[key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)] =
          toSnakeCaseJson(source[key]);
      }
    }
    return result;
  }
  throw new TypeError(
    `workflow_plan_mock_compare_value_not_json:${typeof value}`,
  );
}

function appendOrderedChange(
  changes: WorkflowPlanCompareChange[],
  field: string,
  before: string[],
  after: string[],
): void {
  if (JSON.stringify(before) !== JSON.stringify(after)) {
    changes.push({ field, before, after });
  }
}

function section(
  key: string,
  changes: WorkflowPlanCompareChange[],
): WorkflowPlanCompareSection | null {
  return changes.length > 0 ? { key, changes } : null;
}

function canonicalize(value: unknown): PlannerJsonValue {
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return value;
  }
  if (value === undefined) {
    return null;
  }
  if (Array.isArray(value)) {
    return value
      .map(canonicalize)
      .sort((left, right) =>
        canonicalJson(left).localeCompare(canonicalJson(right)),
      );
  }
  if (typeof value === "object") {
    const source = value as Record<string, unknown>;
    const result: Record<string, PlannerJsonValue> = {};
    for (const key of Object.keys(source).sort(compareStrings)) {
      if (source[key] !== undefined) {
        result[key] = canonicalize(source[key]);
      }
    }
    return result;
  }
  throw new TypeError(
    `workflow_plan_mock_compare_value_not_json:${typeof value}`,
  );
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

function compareStrings(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function fixturePlanningInput(term: string): PlanningInput {
  return {
    flowMode: "batch_research",
    scopes: [
      {
        scopeRef: "fixture-scope",
        scopeType: "topic",
        canonicalTerm: term,
        aliases: [],
        includeTerms: [],
        excludeTerms: [],
        officialAccounts: [],
        seedUrls: [],
        languages: ["en"],
        regions: ["US"],
        platforms: ["reddit"],
        matchMode: "phrase",
      },
    ],
    defaultLanguages: ["en"],
    defaultRegions: ["US"],
    defaultPlatforms: ["reddit"],
    deliveryIntent: { outputs: ["dataset"] },
    policyProfile: "market_monitoring_balanced",
    purpose: "market_research",
    requiredFields: ["id", "url", "text"],
    optionalFields: ["author"],
    budgetCeiling: null,
    rateLimitIntent: null,
    retentionIntent: { days: 30 },
    allowPartialDegradation: true,
  };
}

function saveFixtureTriggered(
  projectId: string,
  input: PlanningInput,
  reservedTerm: string,
): boolean {
  return (
    process.env.NEXT_PUBLIC_MOCK_API === "true" &&
    fixtureModeEnabled() &&
    projectId === WORKFLOW_PLAN_PERSISTENCE_TEST_FIXTURE_PROJECT_ID &&
    input.scopes.some(
      (scope) =>
        scope.canonicalTerm !== null &&
        canonicalEditableText(scope.canonicalTerm) === reservedTerm,
    )
  );
}

async function injectVersionConflictFixture(
  projectId: string,
  planId: string,
  sourceInput: PlanningInput,
): Promise<void> {
  const firstScope = sourceInput.scopes[0];
  if (!firstScope) {
    throw new Error("workflow_plan_conflict_fixture_scope_missing");
  }
  const remoteInput = clone(sourceInput);
  remoteInput.scopes[0] = {
    ...remoteInput.scopes[0],
    canonicalTerm: E2E_VERSION_CONFLICT_REMOTE_TERM,
  };
  const stored = getStoredPlan(projectId, planId);
  const remotePreview = await buildMockWorkflowPlanPreview(
    projectId,
    remoteInput,
  );
  versionConflictFixturePlanIds.add(planId);
  try {
    await createWorkflowVersionInternal(projectId, planId, {
      previewInput: remoteInput,
      expectedPreviewFingerprint: remotePreview.previewFingerprint,
      expectedCurrentVersionId: stored.plan.currentVersionId,
      idempotencyKey: `fixture-conflict-winner-${planId}`,
    });
  } catch (error) {
    versionConflictFixturePlanIds.delete(planId);
    throw error;
  }
}

function mockError(
  status: number,
  code: string,
  details: Record<string, string | number | boolean | null> | null = null,
): ApiRequestError {
  return new ApiRequestError(status, code, {
    code: stableMockErrorCode(code),
    details,
  });
}

function stableMockErrorCode(code: string): ApiErrorCode {
  if (
    code === "workflow_plan_name_invalid" ||
    code === "idempotency_key_invalid" ||
    code === "pagination_invalid"
  ) {
    return "validation_error";
  }
  if (
    code === "mock_api_disabled" ||
    code === "workflow_plan_fixture_disabled"
  ) {
    return "persistence_unavailable";
  }
  switch (code) {
    case "workflow_plan_not_found":
    case "workflow_version_not_found":
    case "preview_stale":
    case "version_conflict":
    case "idempotency_conflict":
    case "workflow_plan_flow_mode_conflict":
      return code;
    default:
      return "workflow_planner_internal_error";
  }
}

function assertTestHelperUsage(): void {
  if (process.env.NODE_ENV !== "test") {
    throw mockError(503, "workflow_plan_test_helper_unavailable");
  }
}

function clone<T>(value: T): T {
  if (typeof globalThis.structuredClone === "function") {
    return globalThis.structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value)) as T;
}
