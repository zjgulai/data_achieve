import { buildMockCapabilityDiscoveryPreviewDto } from "@/lib/capability-discovery-mock";
import type { CapabilityImplementationDto } from "@/types/capability";
import type {
  CapabilityGovernanceCandidateDetailResponseDto,
  CapabilityGovernanceCandidateDto,
  CapabilityGovernanceCandidateListResponseDto,
  CapabilityGovernanceCanonicalAssertionDto,
  CapabilityGovernanceDecisionDto,
  CapabilityGovernanceImportRequestDto,
  CapabilityGovernanceImportResponseDto,
  CapabilityGovernancePermissionSet,
  CapabilityGovernancePermissionSetDto,
  CapabilityGovernancePublicationDetailResponseDto,
  CapabilityGovernancePublicationListResponseDto,
  CapabilityGovernancePublicationRequestDto,
  CapabilityGovernancePublicationResponseDto,
  CapabilityGovernancePublicationRevisionDto,
  CapabilityGovernanceReviewRequestDto,
  CapabilityGovernanceReviewResponseDto,
  CapabilityGovernanceRollbackRequestDto,
  CapabilityGovernanceVerificationTaskDetailResponseDto,
  CapabilityGovernanceVerificationTaskDto,
  CapabilityGovernanceVerificationTaskListResponseDto,
  CapabilityGovernanceVerificationTaskStatus,
} from "@/types/capability-governance";

const NOW = "2026-07-14T09:00:00Z";
const REVIEWED_AT = "2026-07-14T09:15:00Z";
const PUBLISHED_AT = "2026-07-14T09:30:00Z";
const REVIEWER_ID = deterministicUuid(900);
const PUBLISHER_ID = deterministicUuid(901);

function deterministicUuid(index: number): string {
  return `00000000-0000-4000-8000-${index.toString().padStart(12, "0")}`;
}

function fingerprint(index: number): string {
  const digit = ((index % 15) + 1).toString(16);
  return `sha256:${digit.repeat(64)}`;
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function permissionDto(
  value: CapabilityGovernancePermissionSet,
): CapabilityGovernancePermissionSetDto {
  return {
    can_read: value.canRead,
    can_review: value.canReview,
    can_publish: value.canPublish,
  };
}

function seedCandidates(): CapabilityGovernanceCandidateDto[] {
  const preview = buildMockCapabilityDiscoveryPreviewDto();
  const proposedById = new Map(
    preview.proposed_implementations.map((item) => [
      item.proposed_implementation_id,
      item,
    ]),
  );
  return preview.candidate_assertions.map((candidate, index) => {
    const proposed = proposedById.get(candidate.proposed_implementation_id);
    if (!proposed) throw new Error("mock_proposed_implementation_missing");
    return {
      id: deterministicUuid(100 + index),
      candidate_key: fingerprint(100 + index),
      semantic_version: 1,
      candidate_fingerprint: candidate.candidate_fingerprint,
      predecessor_id: null,
      proposed_implementation: {
        schema_version: proposed.schema_version,
        proposed_implementation_id: proposed.proposed_implementation_id,
        provider_id: proposed.provider_id,
        platform: proposed.platform,
        access_channel: proposed.access_channel,
        delivery_form: proposed.delivery_form,
        deployment_mode: proposed.deployment_mode,
        source_label: proposed.source_label,
        claimed_auth_mode: proposed.claimed_auth_mode,
        claimed_required_credentials: [
          ...proposed.claimed_required_credentials,
        ],
        claimed_limitations: [...proposed.claimed_limitations],
      },
      candidate_assertion: {
        schema_version: candidate.schema_version,
        candidate_id: candidate.candidate_id,
        proposed_implementation_id: candidate.proposed_implementation_id,
        platform: candidate.platform,
        access_channel: candidate.access_channel,
        resource_type: candidate.resource_type,
        operation: candidate.operation,
        support_status: candidate.support_status,
        verification_status: candidate.verification_status,
        executable: candidate.executable,
        publishable: candidate.publishable,
        claimed_field_contract: clone(candidate.claimed_field_contract),
        claimed_constraints: clone(candidate.claimed_constraints),
        region_scope: [...candidate.region_scope],
        purpose_scope: [...candidate.purpose_scope],
        auth_scope: [...candidate.auth_scope],
        parser_id: candidate.parser_id,
        candidate_fingerprint: candidate.candidate_fingerprint,
      },
      first_seen_batch_id: deterministicUuid(200),
      created_at: NOW,
    };
  });
}

function seedTasks(
  candidates: CapabilityGovernanceCandidateDto[],
): CapabilityGovernanceVerificationTaskDto[] {
  return candidates.map((candidate, index) => ({
    id: deterministicUuid(300 + index),
    candidate_version_id: candidate.id,
    task_type: "initial_review",
    status: "open",
    task_version: 1,
    opened_at: NOW,
    resolved_at: null,
    decision_id: null,
  }));
}

export function buildMockCapabilityGovernanceCandidateListDto(): CapabilityGovernanceCandidateListResponseDto {
  return {
    schema_version: "capability_governance_candidate_list.v1",
    permissions: {
      can_read: true,
      can_review: true,
      can_publish: true,
    },
    items: seedCandidates(),
    limit: 50,
    offset: 0,
  };
}

export function buildMockCapabilityGovernanceCanonicalBundleDto(): {
  implementation: CapabilityImplementationDto;
  assertion: CapabilityGovernanceCanonicalAssertionDto;
} {
  const preview = buildMockCapabilityDiscoveryPreviewDto();
  const candidate = preview.candidate_assertions[0];
  const proposed = preview.proposed_implementations.find(
    (item) =>
      item.proposed_implementation_id === candidate?.proposed_implementation_id,
  );
  const evidenceRef = candidate?.evidence_refs[0];
  if (!candidate || !proposed || !evidenceRef) {
    throw new Error("mock_canonical_bundle_seed_invalid");
  }
  const implementationId = "mock.governance.reviewed.v1";
  const implementation: CapabilityImplementationDto = {
    schema_version: "capability_implementation.v1",
    implementation_id: implementationId,
    provider_id: proposed.provider_id,
    platform: proposed.platform,
    access_channel: proposed.access_channel,
    delivery_form: proposed.delivery_form,
    deployment_mode: proposed.deployment_mode,
    data_domains: ["social_public_content"],
    resource_groups: ["ugc_posts"],
    official_docs: ["https://example.com/mock-governance-doc"],
    sdk_selection: null,
    live_adapter_strategy: "fixture_only",
    auth_mode: proposed.claimed_auth_mode,
    quota_hint: {},
    cost_hint: {},
    policy_flags: ["fixture_only"],
    blocked_actions: ["provider_call"],
    stability: "medium",
    self_host_priority: "not_applicable",
    api_version: "mock-v1",
    required_credentials: [...proposed.claimed_required_credentials],
    supported_endpoints: [candidate.operation],
    lifecycle_status: "active",
  };
  const assertion: CapabilityGovernanceCanonicalAssertionDto = {
    assertion_id: "mock.governance.assertion.v1",
    implementation_id: implementationId,
    resource_type: candidate.resource_type,
    operation: candidate.operation,
    support_status: "verified",
    source_resource_group: "ugc_posts",
    region_scope: [...candidate.region_scope],
    purpose_scope: [...candidate.purpose_scope],
    auth_scope: [...candidate.auth_scope],
    field_contract: clone(candidate.claimed_field_contract),
    constraints: clone(candidate.claimed_constraints),
    score_profile: {
      coverage: 1,
      reliability: 1,
      freshness: 1,
      compliance: 1,
      cost_efficiency: 1,
    },
    evidence_refs: [evidenceRef],
  };
  return { implementation, assertion };
}

export class CapabilityGovernanceMockError extends Error {
  status: number;

  constructor(code: string, status: number) {
    super(code);
    this.name = "CapabilityGovernanceMockError";
    this.status = status;
  }
}

type IdempotencyEntry = {
  request: string;
  response:
    | CapabilityGovernanceImportResponseDto
    | CapabilityGovernanceReviewResponseDto
    | CapabilityGovernancePublicationResponseDto;
};

export type CapabilityGovernanceMockSnapshot = {
  candidates: CapabilityGovernanceCandidateDto[];
  tasks: CapabilityGovernanceVerificationTaskDto[];
  decisions: CapabilityGovernanceDecisionDto[];
  revisions: CapabilityGovernancePublicationRevisionDto[];
  currentRevisionId: string | null;
};

export type CapabilityGovernanceMockStore = ReturnType<
  typeof createMockCapabilityGovernanceStore
>;

export function createMockCapabilityGovernanceStore(
  options: {
    permissions?: CapabilityGovernancePermissionSet;
  } = {},
) {
  const permissions = options.permissions ?? {
    canRead: true,
    canReview: true,
    canPublish: true,
  };
  const candidates = seedCandidates();
  const tasks = seedTasks(candidates);
  const evidence = buildMockCapabilityDiscoveryPreviewDto().evidence;
  const decisions: CapabilityGovernanceDecisionDto[] = [];
  const revisions: CapabilityGovernancePublicationRevisionDto[] = [];
  const idempotency = new Map<string, IdempotencyEntry>();
  let currentRevisionId: string | null = null;
  let requestSequence = 1;

  function requirePermission(
    permission: keyof CapabilityGovernancePermissionSet,
  ) {
    if (!permissions[permission]) {
      throw new CapabilityGovernanceMockError(
        "capability_governance_forbidden",
        403,
      );
    }
  }

  function paginate<T>(items: T[], limit: number, offset: number): T[] {
    return items.slice(offset, offset + limit).map(clone);
  }

  function replay<T extends IdempotencyEntry["response"]>(
    scope: string,
    key: string,
    payload: object,
  ): T | null {
    const normalized = normalizedKey(key);
    const request = JSON.stringify(payload);
    const existing = idempotency.get(`${scope}:${normalized}`);
    if (!existing) return null;
    if (existing.request !== request) {
      throw new CapabilityGovernanceMockError("idempotency_conflict", 409);
    }
    return {
      ...clone(existing.response),
      database_write: false,
      domain_changed: false,
      idempotent_replay: true,
    } as T;
  }

  function remember(
    scope: string,
    key: string,
    payload: object,
    response: IdempotencyEntry["response"],
  ) {
    idempotency.set(`${scope}:${normalizedKey(key)}`, {
      request: JSON.stringify(payload),
      response: clone(response),
    });
  }

  function nextRequestId(): string {
    const value = deterministicUuid(700 + requestSequence);
    requestSequence += 1;
    return value;
  }

  function normalizedKey(value: string): string {
    const normalized = value.trim();
    if (normalized.length < 12 || normalized.length > 200) {
      throw new CapabilityGovernanceMockError("idempotency_key_invalid", 422);
    }
    return normalized;
  }

  return {
    snapshot(): CapabilityGovernanceMockSnapshot {
      return clone({
        candidates,
        tasks,
        decisions,
        revisions,
        currentRevisionId,
      });
    },

    listCandidates({
      limit,
      offset,
    }: {
      limit: number;
      offset: number;
    }): CapabilityGovernanceCandidateListResponseDto {
      requirePermission("canRead");
      return {
        schema_version: "capability_governance_candidate_list.v1",
        permissions: permissionDto(permissions),
        items: paginate(candidates, limit, offset),
        limit,
        offset,
      };
    },

    getCandidate(
      candidateKey: string,
    ): CapabilityGovernanceCandidateDetailResponseDto {
      requirePermission("canRead");
      const candidate = candidates.find(
        (item) => item.candidate_key === candidateKey,
      );
      if (!candidate) {
        throw new CapabilityGovernanceMockError(
          "governance_resource_not_found",
          404,
        );
      }
      const task = tasks.find(
        (item) =>
          item.candidate_version_id === candidate.id && item.status === "open",
      );
      const decision = decisions
        .filter((item) => item.candidate_version_id === candidate.id)
        .at(-1);
      return {
        schema_version: "capability_governance_candidate_detail.v1",
        candidate: clone(candidate),
        evidence: clone(evidence),
        open_verification_task: task ? clone(task) : null,
        latest_decision: decision ? clone(decision) : null,
      };
    },

    listVerificationTasks({
      status,
      limit,
      offset,
    }: {
      status?: CapabilityGovernanceVerificationTaskStatus;
      limit: number;
      offset: number;
    }): CapabilityGovernanceVerificationTaskListResponseDto {
      requirePermission("canRead");
      const filtered = status
        ? tasks.filter((task) => task.status === status)
        : tasks;
      return {
        schema_version: "capability_governance_verification_task_list.v1",
        items: paginate(filtered, limit, offset),
        limit,
        offset,
      };
    },

    getVerificationTask(
      taskId: string,
    ): CapabilityGovernanceVerificationTaskDetailResponseDto {
      requirePermission("canRead");
      const task = tasks.find((item) => item.id === taskId);
      if (!task) {
        throw new CapabilityGovernanceMockError(
          "governance_resource_not_found",
          404,
        );
      }
      const candidate = candidates.find(
        (item) => item.id === task.candidate_version_id,
      );
      if (!candidate) throw new Error("mock_task_candidate_missing");
      const decision = task.decision_id
        ? decisions.find((item) => item.id === task.decision_id)
        : null;
      return {
        schema_version: "capability_governance_verification_task_detail.v1",
        task: clone(task),
        candidate: clone(candidate),
        evidence: clone(evidence),
        decision: decision ? clone(decision) : null,
      };
    },

    listPublications({
      limit,
      offset,
    }: {
      limit: number;
      offset: number;
    }): CapabilityGovernancePublicationListResponseDto {
      requirePermission("canRead");
      const ordered = [...revisions].sort(
        (left, right) => right.revision_number - left.revision_number,
      );
      return {
        schema_version: "capability_governance_publication_list.v1",
        items: paginate(ordered, limit, offset).map((item) => ({
          ...item,
          is_current: item.id === currentRevisionId,
        })),
        current_revision_id: currentRevisionId,
        limit,
        offset,
      };
    },

    getPublication(
      revisionId: string,
    ): CapabilityGovernancePublicationDetailResponseDto {
      requirePermission("canRead");
      const revision = revisions.find((item) => item.id === revisionId);
      if (!revision) {
        throw new CapabilityGovernanceMockError(
          "governance_resource_not_found",
          404,
        );
      }
      return {
        schema_version: "capability_governance_publication_detail.v1",
        revision: {
          ...clone(revision),
          is_current: revision.id === currentRevisionId,
        },
        current_revision_id: currentRevisionId,
      };
    },

    importCandidates(
      payload: CapabilityGovernanceImportRequestDto,
      key: string,
    ): CapabilityGovernanceImportResponseDto {
      requirePermission("canReview");
      const replayed = replay<CapabilityGovernanceImportResponseDto>(
        "import",
        key,
        payload,
      );
      if (replayed) return replayed;
      const response: CapabilityGovernanceImportResponseDto = {
        schema_version: "capability_governance_import_response.v1",
        request_id: nextRequestId(),
        batch_id: null,
        preview_fingerprint: payload.expected_preview_fingerprint,
        outcome: "semantic_exact_replay",
        candidates: candidates.map((candidate, index) => ({
          candidate_key: candidate.candidate_key,
          candidate_version_id: candidate.id,
          semantic_version: candidate.semantic_version,
          classification: "semantic_exact_replay",
          verification_task_id: tasks[index]?.id ?? null,
          evidence_added_count: 0,
        })),
        database_write: true,
        domain_changed: false,
        idempotent_replay: false,
        provider_call: false,
        actor_run: false,
        browser_run: false,
        llm_call: false,
        workflow_run_created: false,
        database_migration: false,
        production_write_allowed: false,
      };
      remember("import", key, payload, response);
      return clone(response);
    },

    reviewCandidate(
      taskId: string,
      payload: CapabilityGovernanceReviewRequestDto,
      key: string,
    ): CapabilityGovernanceReviewResponseDto {
      requirePermission("canReview");
      const scope = `review:${taskId}`;
      const replayed = replay<CapabilityGovernanceReviewResponseDto>(
        scope,
        key,
        payload,
      );
      if (replayed) return replayed;
      const task = tasks.find((item) => item.id === taskId);
      if (
        !task ||
        task.status !== "open" ||
        task.task_version !== payload.expected_task_version
      ) {
        throw new CapabilityGovernanceMockError(
          "verification_task_conflict",
          409,
        );
      }
      const decisionId = deterministicUuid(400 + decisions.length);
      const decision: CapabilityGovernanceDecisionDto = {
        id: decisionId,
        verification_task_id: task.id,
        candidate_version_id: task.candidate_version_id,
        action: payload.action,
        verification_status:
          payload.action === "reject" ? "rejected" : "verified",
        reviewer_user_id: REVIEWER_ID,
        reviewed_at: REVIEWED_AT,
        reason: payload.reason,
        canonical_bundle:
          payload.action === "reject"
            ? null
            : {
                implementation: clone(payload.canonical_implementation),
                assertion: clone(payload.canonical_assertion),
              },
      };
      decisions.push(decision);
      task.status = "resolved";
      task.resolved_at = REVIEWED_AT;
      task.decision_id = decisionId;
      const response: CapabilityGovernanceReviewResponseDto = {
        schema_version: "capability_governance_review_response.v1",
        request_id: nextRequestId(),
        decision_id: decisionId,
        task_id: task.id,
        candidate_version_id: task.candidate_version_id,
        task_version: task.task_version,
        action: payload.action,
        verification_status: decision.verification_status,
        reviewed_at: REVIEWED_AT,
        database_write: true,
        domain_changed: true,
        idempotent_replay: false,
        provider_call: false,
        actor_run: false,
        browser_run: false,
        llm_call: false,
        workflow_run_created: false,
        database_migration: false,
        production_write_allowed: false,
      };
      remember(scope, key, payload, response);
      return clone(response);
    },

    publishCatalog(
      payload: CapabilityGovernancePublicationRequestDto,
      key: string,
    ): CapabilityGovernancePublicationResponseDto {
      requirePermission("canPublish");
      const replayed = replay<CapabilityGovernancePublicationResponseDto>(
        "publish",
        key,
        payload,
      );
      if (replayed) return replayed;
      if (payload.expected_parent_revision_id !== currentRevisionId) {
        throw new CapabilityGovernanceMockError(
          "publication_parent_conflict",
          409,
        );
      }
      for (const operation of payload.operations) {
        if (
          !decisions.some(
            (decision) =>
              decision.id === operation.verification_decision_id &&
              decision.verification_status === "verified",
          )
        ) {
          throw new CapabilityGovernanceMockError(
            "publication_contract_invalid",
            422,
          );
        }
      }
      const revisionNumber = revisions.length + 1;
      const revisionId = deterministicUuid(500 + revisionNumber);
      const revision: CapabilityGovernancePublicationRevisionDto = {
        id: revisionId,
        revision_number: revisionNumber,
        parent_revision_id: currentRevisionId,
        restored_from_revision_id: null,
        catalog_snapshot_id: fingerprint(500),
        publisher_user_id: PUBLISHER_ID,
        published_at: PUBLISHED_AT,
        reason: payload.reason,
        operations: clone(payload.operations),
        is_current: true,
      };
      revisions.forEach((item) => {
        item.is_current = false;
      });
      revisions.push(revision);
      currentRevisionId = revisionId;
      const response = publicationResponse(revision, "publish");
      remember("publish", key, payload, response);
      return clone(response);
    },

    rollbackCatalog(
      payload: CapabilityGovernanceRollbackRequestDto,
      key: string,
    ): CapabilityGovernancePublicationResponseDto {
      requirePermission("canPublish");
      const replayed = replay<CapabilityGovernancePublicationResponseDto>(
        "rollback",
        key,
        payload,
      );
      if (replayed) return replayed;
      if (payload.expected_current_revision_id !== currentRevisionId) {
        throw new CapabilityGovernanceMockError(
          "publication_parent_conflict",
          409,
        );
      }
      const target = revisions.find(
        (item) => item.id === payload.target_revision_id,
      );
      if (!target || target.id === currentRevisionId) {
        throw new CapabilityGovernanceMockError(
          "publication_contract_invalid",
          422,
        );
      }
      const revisionNumber = revisions.length + 1;
      const revisionId = deterministicUuid(500 + revisionNumber);
      const revision: CapabilityGovernancePublicationRevisionDto = {
        id: revisionId,
        revision_number: revisionNumber,
        parent_revision_id: currentRevisionId,
        restored_from_revision_id: target.id,
        catalog_snapshot_id: target.catalog_snapshot_id,
        publisher_user_id: PUBLISHER_ID,
        published_at: PUBLISHED_AT,
        reason: payload.reason,
        operations: [{ operation: "rollback", target_revision_id: target.id }],
        is_current: true,
      };
      revisions.forEach((item) => {
        item.is_current = false;
      });
      revisions.push(revision);
      currentRevisionId = revisionId;
      const response = publicationResponse(revision, "rollback");
      remember("rollback", key, payload, response);
      return clone(response);
    },
  };

  function publicationResponse(
    revision: CapabilityGovernancePublicationRevisionDto,
    kind: "publish" | "rollback",
  ): CapabilityGovernancePublicationResponseDto {
    return {
      schema_version: "capability_governance_publication_response.v1",
      publication_kind: kind,
      request_id: nextRequestId(),
      revision_id: revision.id,
      revision_number: revision.revision_number,
      parent_revision_id: revision.parent_revision_id,
      restored_from_revision_id: revision.restored_from_revision_id,
      catalog_snapshot_id: revision.catalog_snapshot_id,
      head_version: revision.revision_number,
      operation_count: revision.operations.length,
      published_at: revision.published_at,
      database_write: true,
      domain_changed: true,
      idempotent_replay: false,
      provider_call: false,
      actor_run: false,
      browser_run: false,
      llm_call: false,
      workflow_run_created: false,
      database_migration: false,
      production_write_allowed: false,
    };
  }
}
