import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildCapabilityGovernanceImportRequest,
  buildCapabilityGovernancePublicationRequest,
  buildCapabilityGovernanceReviewRequest,
  buildCapabilityGovernanceRollbackRequest,
  mapCapabilityGovernanceCandidateList,
} from "@/lib/api/capability-governance";
import {
  buildMockCapabilityGovernanceCandidateListDto,
  buildMockCapabilityGovernanceCanonicalBundleDto,
  createMockCapabilityGovernanceStore,
} from "@/lib/capability-governance-mock";

const PREVIEW_FINGERPRINT = `sha256:${"d".repeat(64)}`;

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.resetModules();
});

describe("capability governance contracts", () => {
  it("maps nested snake_case DTOs and explicit permission state", () => {
    const dto = buildMockCapabilityGovernanceCandidateListDto();
    const result = mapCapabilityGovernanceCandidateList(dto);

    expect(result.schemaVersion).toBe(
      "capability_governance_candidate_list.v1",
    );
    expect(result.permissions).toEqual({
      canRead: true,
      canReview: true,
      canPublish: true,
    });
    expect(result.items[0]).toMatchObject({
      candidateKey: dto.items[0]?.candidate_key,
      semanticVersion: dto.items[0]?.semantic_version,
      candidateFingerprint: dto.items[0]?.candidate_fingerprint,
      firstSeenBatchId: dto.items[0]?.first_seen_batch_id,
    });
    expect(result.items[0]?.proposedImplementation).toMatchObject({
      proposedImplementationId:
        dto.items[0]?.proposed_implementation.proposed_implementation_id,
      accessChannel: dto.items[0]?.proposed_implementation.access_channel,
      claimedRequiredCredentials:
        dto.items[0]?.proposed_implementation.claimed_required_credentials,
    });
    expect(result.items[0]?.candidateAssertion).toMatchObject({
      candidateId: dto.items[0]?.candidate_assertion.candidate_id,
      resourceType: dto.items[0]?.candidate_assertion.resource_type,
      claimedFieldContract:
        dto.items[0]?.candidate_assertion.claimed_field_contract,
      candidateFingerprint:
        dto.items[0]?.candidate_assertion.candidate_fingerprint,
    });
  });

  it("builds strict import, review, publication, and rollback bodies", () => {
    const canonical = buildMockCapabilityGovernanceCanonicalBundleDto();
    const importRequest = buildCapabilityGovernanceImportRequest(
      ["tikhub-youtube-market-v1"],
      PREVIEW_FINGERPRINT,
    );
    const rejectRequest = buildCapabilityGovernanceReviewRequest({
      expectedTaskVersion: 1,
      action: "reject",
      reason: "Insufficient evidence.",
    });
    const verifyRequest = buildCapabilityGovernanceReviewRequest({
      expectedTaskVersion: 1,
      action: "verify",
      reason: "Evidence verified.",
      canonicalImplementation: canonical.implementation,
      canonicalAssertion: canonical.assertion,
    });
    const publicationRequest = buildCapabilityGovernancePublicationRequest({
      expectedParentRevisionId: null,
      reason: "Publish verified decision.",
      operations: [
        {
          operation: "upsert_verified_assertion",
          verificationDecisionId: "00000000-0000-4000-8000-000000000101",
        },
      ],
    });
    const rollbackRequest = buildCapabilityGovernanceRollbackRequest({
      expectedCurrentRevisionId: "00000000-0000-4000-8000-000000000202",
      targetRevisionId: "00000000-0000-4000-8000-000000000201",
      reason: "Restore prior revision.",
    });

    expect(importRequest).toEqual({
      schema_version: "capability_governance_import_request.v1",
      fixture_ids: ["tikhub-youtube-market-v1"],
      expected_preview_fingerprint: PREVIEW_FINGERPRINT,
    });
    expect(rejectRequest).toMatchObject({
      action: "reject",
      canonical_implementation: null,
      canonical_assertion: null,
    });
    expect(verifyRequest).toMatchObject({
      action: "verify",
      canonical_implementation: canonical.implementation,
      canonical_assertion: canonical.assertion,
    });
    expect(publicationRequest).toEqual({
      schema_version: "capability_governance_publication_request.v1",
      expected_parent_revision_id: null,
      reason: "Publish verified decision.",
      operations: [
        {
          operation: "upsert_verified_assertion",
          verification_decision_id: "00000000-0000-4000-8000-000000000101",
        },
      ],
    });
    expect(rollbackRequest).toEqual({
      schema_version: "capability_governance_rollback_request.v1",
      expected_current_revision_id: "00000000-0000-4000-8000-000000000202",
      target_revision_id: "00000000-0000-4000-8000-000000000201",
      reason: "Restore prior revision.",
    });
  });

  it("sends every real mutation to its exact path with Idempotency-Key", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    const store = createMockCapabilityGovernanceStore();
    const candidateList = store.listCandidates({ limit: 50, offset: 0 });
    const task = store.listVerificationTasks({
      status: "open",
      limit: 50,
      offset: 0,
    }).items[0];
    expect(task).toBeDefined();
    const canonical = buildMockCapabilityGovernanceCanonicalBundleDto();
    const reviewRequest = buildCapabilityGovernanceReviewRequest({
      expectedTaskVersion: 1,
      action: "verify",
      reason: "Evidence verified.",
      canonicalImplementation: canonical.implementation,
      canonicalAssertion: canonical.assertion,
    });
    const reviewResponse = store.reviewCandidate(
      task?.id ?? "missing",
      reviewRequest,
      "mock-review-response-0001",
    );
    const publishRequest = buildCapabilityGovernancePublicationRequest({
      expectedParentRevisionId: null,
      reason: "Publish reviewed decision.",
      operations: [
        {
          operation: "upsert_verified_assertion",
          verificationDecisionId: reviewResponse.decision_id,
        },
      ],
    });
    const firstPublication = store.publishCatalog(
      publishRequest,
      "mock-publish-response-0001",
    );
    const secondPublication = store.publishCatalog(
      buildCapabilityGovernancePublicationRequest({
        expectedParentRevisionId: firstPublication.revision_id,
        reason: "Append another revision.",
        operations: [
          {
            operation: "upsert_verified_assertion",
            verificationDecisionId: reviewResponse.decision_id,
          },
        ],
      }),
      "mock-publish-response-0002",
    );
    const rollbackRequest = buildCapabilityGovernanceRollbackRequest({
      expectedCurrentRevisionId: secondPublication.revision_id,
      targetRevisionId: firstPublication.revision_id,
      reason: "Restore first revision.",
    });
    const responses = [
      candidateList,
      store.importCandidates(
        buildCapabilityGovernanceImportRequest(
          ["tikhub-youtube-market-v1"],
          PREVIEW_FINGERPRINT,
        ),
        "mock-import-response-0001",
      ),
      reviewResponse,
      firstPublication,
      store.rollbackCatalog(rollbackRequest, "mock-rollback-response-0001"),
    ];
    const fetchMock = vi.fn<typeof fetch>(async () => {
      const response = responses.shift();
      return new Response(JSON.stringify(response), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = await import("@/lib/api/capability-governance");

    await api.listCapabilityGovernanceCandidates();
    await api.importCapabilityGovernanceCandidates(
      buildCapabilityGovernanceImportRequest(
        ["tikhub-youtube-market-v1"],
        PREVIEW_FINGERPRINT,
      ),
      "real-import-key-0001",
    );
    await api.reviewCapabilityGovernanceCandidate(
      task?.id ?? "missing",
      reviewRequest,
      "real-review-key-0001",
    );
    await api.publishCapabilityGovernanceCatalog(
      publishRequest,
      "real-publish-key-0001",
    );
    await api.rollbackCapabilityGovernanceCatalog(
      rollbackRequest,
      "real-rollback-key-0001",
    );

    const expected = [
      ["/api/capabilities/governance/candidates", undefined],
      ["/api/capabilities/governance/imports", "real-import-key-0001"],
      [
        `/api/capabilities/governance/verification-tasks/${task?.id}/decisions`,
        "real-review-key-0001",
      ],
      ["/api/capabilities/governance/publications", "real-publish-key-0001"],
      [
        "/api/capabilities/governance/publications/rollback",
        "real-rollback-key-0001",
      ],
    ] as const;
    expect(fetchMock).toHaveBeenCalledTimes(expected.length);
    for (const [index, [path, key]] of expected.entries()) {
      const [url, init] = fetchMock.mock.calls[index] ?? [];
      expect(url).toBe(`http://localhost:8000${path}`);
      if (key) {
        expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(key);
        expect(init?.method).toBe("POST");
      } else {
        expect(init?.method).toBeUndefined();
      }
    }
  });

  it("uses all six exact real read paths and maps their DTOs", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    const store = createMockCapabilityGovernanceStore();
    const candidateList = store.listCandidates({ limit: 50, offset: 0 });
    const candidate = candidateList.items[0];
    const taskList = store.listVerificationTasks({
      limit: 50,
      offset: 0,
    });
    const task = taskList.items[0];
    expect(candidate).toBeDefined();
    expect(task).toBeDefined();
    const canonical = buildMockCapabilityGovernanceCanonicalBundleDto();
    const reviewed = store.reviewCandidate(
      task?.id ?? "missing",
      buildCapabilityGovernanceReviewRequest({
        expectedTaskVersion: 1,
        action: "verify",
        reason: "Prepare read transport state.",
        canonicalImplementation: canonical.implementation,
        canonicalAssertion: canonical.assertion,
      }),
      "mock-read-review-0001",
    );
    const published = store.publishCatalog(
      buildCapabilityGovernancePublicationRequest({
        expectedParentRevisionId: null,
        reason: "Prepare read Revision state.",
        operations: [
          {
            operation: "upsert_verified_assertion",
            verificationDecisionId: reviewed.decision_id,
          },
        ],
      }),
      "mock-read-publish-0001",
    );
    const responses = [
      candidateList,
      store.getCandidate(candidate?.candidate_key ?? "missing"),
      store.listVerificationTasks({ limit: 50, offset: 0 }),
      store.getVerificationTask(task?.id ?? "missing"),
      store.listPublications({ limit: 50, offset: 0 }),
      store.getPublication(published.revision_id),
    ];
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify(responses.shift()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const api = await import("@/lib/api/capability-governance");

    const mappedCandidates = await api.listCapabilityGovernanceCandidates();
    const mappedCandidate = await api.getCapabilityGovernanceCandidate(
      candidate?.candidate_key ?? "missing",
    );
    const mappedTasks = await api.listCapabilityGovernanceVerificationTasks();
    const mappedTask = await api.getCapabilityGovernanceVerificationTask(
      task?.id ?? "missing",
    );
    const mappedPublications = await api.listCapabilityGovernancePublications();
    const mappedPublication = await api.getCapabilityGovernancePublication(
      published.revision_id,
    );

    expect(mappedCandidates.items[0]?.candidateKey).toBe(
      candidate?.candidate_key,
    );
    expect(mappedCandidate.latestDecision?.id).toBe(reviewed.decision_id);
    expect(mappedTasks.items[0]?.status).toBe("resolved");
    expect(mappedTask.decision?.id).toBe(reviewed.decision_id);
    expect(mappedPublications.currentRevisionId).toBe(published.revision_id);
    expect(mappedPublication.revision.isCurrent).toBe(true);
    const expectedPaths = [
      "/api/capabilities/governance/candidates",
      `/api/capabilities/governance/candidates/${encodeURIComponent(candidate?.candidate_key ?? "missing")}`,
      "/api/capabilities/governance/verification-tasks",
      `/api/capabilities/governance/verification-tasks/${task?.id}`,
      "/api/capabilities/governance/publications",
      `/api/capabilities/governance/publications/${published.revision_id}`,
    ];
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(
      expectedPaths.map((path) => `http://localhost:8000${path}`),
    );
  });

  it("propagates a real governance conflict without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "false");
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ detail: "verification_task_conflict" }), {
          status: 409,
          headers: {
            "Content-Type": "application/json",
            "X-Request-ID": "request-conflict-001",
          },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const api = await import("@/lib/api/capability-governance");

    await expect(
      api.reviewCapabilityGovernanceCandidate(
        "00000000-0000-4000-8000-000000000301",
        buildCapabilityGovernanceReviewRequest({
          expectedTaskVersion: 1,
          action: "reject",
          reason: "Reject stale task.",
        }),
        "real-conflict-key-0001",
      ),
    ).rejects.toMatchObject({
      name: "ApiRequestError",
      status: 409,
      code: "verification_task_conflict",
      requestId: "request-conflict-001",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("capability governance mock state", () => {
  it("is deterministic, fresh, and models permission states", () => {
    const first = createMockCapabilityGovernanceStore();
    const second = createMockCapabilityGovernanceStore();

    expect(first.snapshot()).toEqual(second.snapshot());
    expect(first.snapshot()).not.toBe(second.snapshot());

    const readOnly = createMockCapabilityGovernanceStore({
      permissions: { canRead: true, canReview: false, canPublish: false },
    });
    expect(
      readOnly.listCandidates({ limit: 50, offset: 0 }).permissions,
    ).toEqual({
      can_read: true,
      can_review: false,
      can_publish: false,
    });
    const task = readOnly.listVerificationTasks({
      status: "open",
      limit: 50,
      offset: 0,
    }).items[0];
    expect(() =>
      readOnly.reviewCandidate(
        task?.id ?? "missing",
        buildCapabilityGovernanceReviewRequest({
          expectedTaskVersion: 1,
          action: "reject",
          reason: "Read-only cannot review.",
        }),
        "mock-read-only-review-0001",
      ),
    ).toThrowError("capability_governance_forbidden");
  });

  it("models idempotent review, task conflict, parent conflict, and rollback", () => {
    const store = createMockCapabilityGovernanceStore();
    const task = store.listVerificationTasks({
      status: "open",
      limit: 50,
      offset: 0,
    }).items[0];
    expect(task).toBeDefined();
    const canonical = buildMockCapabilityGovernanceCanonicalBundleDto();
    const reviewRequest = buildCapabilityGovernanceReviewRequest({
      expectedTaskVersion: 1,
      action: "verify",
      reason: "Verified in deterministic mock.",
      canonicalImplementation: canonical.implementation,
      canonicalAssertion: canonical.assertion,
    });
    const reviewKey = "mock-idempotent-review-0001";
    const reviewed = store.reviewCandidate(
      task?.id ?? "missing",
      reviewRequest,
      reviewKey,
    );
    const replay = store.reviewCandidate(
      task?.id ?? "missing",
      reviewRequest,
      reviewKey,
    );

    expect(reviewed.database_write).toBe(true);
    expect(replay).toMatchObject({
      decision_id: reviewed.decision_id,
      database_write: false,
      domain_changed: false,
      idempotent_replay: true,
    });
    expect(() =>
      store.reviewCandidate(
        task?.id ?? "missing",
        { ...reviewRequest, reason: "Changed request." },
        reviewKey,
      ),
    ).toThrowError("idempotency_conflict");
    expect(() =>
      store.reviewCandidate(
        task?.id ?? "missing",
        reviewRequest,
        "mock-stale-task-review-0001",
      ),
    ).toThrowError("verification_task_conflict");

    const publishRequest = buildCapabilityGovernancePublicationRequest({
      expectedParentRevisionId: null,
      reason: "Publish deterministic Decision.",
      operations: [
        {
          operation: "upsert_verified_assertion",
          verificationDecisionId: reviewed.decision_id,
        },
      ],
    });
    const firstRevision = store.publishCatalog(
      publishRequest,
      "mock-first-publish-0001",
    );
    expect(() =>
      store.publishCatalog(publishRequest, "mock-parent-conflict-0001"),
    ).toThrowError("publication_parent_conflict");
    const secondRevision = store.publishCatalog(
      buildCapabilityGovernancePublicationRequest({
        expectedParentRevisionId: firstRevision.revision_id,
        reason: "Append deterministic Revision.",
        operations: [
          {
            operation: "upsert_verified_assertion",
            verificationDecisionId: reviewed.decision_id,
          },
        ],
      }),
      "mock-second-publish-0001",
    );
    const restored = store.rollbackCatalog(
      buildCapabilityGovernanceRollbackRequest({
        expectedCurrentRevisionId: secondRevision.revision_id,
        targetRevisionId: firstRevision.revision_id,
        reason: "Restore first deterministic Revision.",
      }),
      "mock-rollback-0001",
    );

    expect(restored).toMatchObject({
      publication_kind: "rollback",
      revision_number: 3,
      parent_revision_id: secondRevision.revision_id,
      restored_from_revision_id: firstRevision.revision_id,
    });
    expect(
      store
        .listPublications({ limit: 50, offset: 0 })
        .items.map((item) => item.revision_number),
    ).toEqual([3, 2, 1]);
  });

  it("uses mock state without fetch when mock mode is explicit", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    const fetchMock = vi.fn(async () => {
      throw new Error("fetch must not run in governance mock mode");
    });
    vi.stubGlobal("fetch", fetchMock);
    const api = await import("@/lib/api/capability-governance");

    const result = await api.listCapabilityGovernanceCandidates();

    expect(result.permissions.canReview).toBe(true);
    expect(result.items.length).toBeGreaterThan(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps governance browser fixtures inert unless their dedicated flag is true", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    vi.stubEnv("NEXT_PUBLIC_CAPABILITY_GOVERNANCE_TEST_FIXTURES", "false");
    vi.stubGlobal("window", {
      location: { search: "?governance_fixture=forbidden" },
    });
    vi.resetModules();
    const api = await import("@/lib/api/capability-governance");

    const result = await api.listCapabilityGovernanceCandidates();

    expect(result.permissions).toEqual({
      canRead: true,
      canReview: true,
      canPublish: true,
    });
  });

  it("exposes a fail-closed forbidden fixture only behind the dedicated browser flag", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    vi.stubEnv("NEXT_PUBLIC_CAPABILITY_GOVERNANCE_TEST_FIXTURES", "true");
    vi.stubGlobal("window", {
      location: { search: "?governance_fixture=forbidden" },
    });
    vi.resetModules();
    const api = await import("@/lib/api/capability-governance");

    await expect(
      api.listCapabilityGovernanceCandidates(),
    ).rejects.toMatchObject({
      status: 403,
      message: "capability_governance_forbidden",
    });
  });

  it("keeps the review-conflict fixture open so the UI can reload authoritative state", async () => {
    vi.stubEnv("NEXT_PUBLIC_MOCK_API", "true");
    vi.stubEnv("NEXT_PUBLIC_CAPABILITY_GOVERNANCE_TEST_FIXTURES", "true");
    vi.stubGlobal("window", {
      location: { search: "?governance_fixture=review-conflict" },
    });
    vi.resetModules();
    const api = await import("@/lib/api/capability-governance");
    const task = (await api.listCapabilityGovernanceVerificationTasks())
      .items[0];
    expect(task).toBeDefined();
    const canonical = buildMockCapabilityGovernanceCanonicalBundleDto();

    await expect(
      api.reviewCapabilityGovernanceCandidate(
        task?.id ?? "missing",
        api.buildCapabilityGovernanceReviewRequest({
          action: "verify",
          expectedTaskVersion: task?.taskVersion ?? 0,
          reason: "Exercise the browser conflict fixture.",
          canonicalImplementation: canonical.implementation,
          canonicalAssertion: canonical.assertion,
        }),
        "browser-review-conflict-0001",
      ),
    ).rejects.toMatchObject({
      status: 409,
      message: "verification_task_conflict",
    });
    expect(
      (await api.listCapabilityGovernanceVerificationTasks()).items[0],
    ).toMatchObject({ status: "open", taskVersion: 1 });
  });
});
