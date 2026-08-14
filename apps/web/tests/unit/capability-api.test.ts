import { describe, expect, it } from "vitest";

import {
  buildCapabilityQuery,
  mapCapabilityImplementationDetail,
  mapCapabilityMatrixResponse,
} from "@/lib/api/capabilities";
import {
  buildMockCapabilityAssertions,
  buildMockCapabilityEvidence,
  buildMockCapabilityImplementationDetailDto,
  buildMockCapabilityImplementations,
  buildMockCapabilityMatrixDto,
} from "@/lib/capability-mock";

describe("capability API", () => {
  it("maps the complete mock capability matrix", () => {
    const matrix = mapCapabilityMatrixResponse(buildMockCapabilityMatrixDto());

    expect(matrix.cells).toHaveLength(42);
    expect(matrix.summary.populatedCellCount).toBe(7);
    expect(matrix.summary.unknownCellCount).toBe(35);
    expect(matrix.providerCall).toBe(false);
    expect(matrix.productionWriteAllowed).toBe(false);
    expect(matrix.accessChannels).toHaveLength(6);
  });

  it("distinguishes candidate official API support from unknown browser support", () => {
    const matrix = mapCapabilityMatrixResponse(buildMockCapabilityMatrixDto());
    const officialApiCell = matrix.cells.find(
      (cell) =>
        cell.platform === "youtube" &&
        cell.accessChannel === "official_authorized_api",
    );
    const authorizedBrowserCell = matrix.cells.find(
      (cell) =>
        cell.platform === "youtube" &&
        cell.accessChannel === "authorized_browser",
    );

    expect(officialApiCell?.summaryStatus).toBe("candidate");
    expect(authorizedBrowserCell?.summaryStatus).toBe("unknown");
  });

  it("maps implementation details without exposing credential values", () => {
    const detail = mapCapabilityImplementationDetail(
      buildMockCapabilityImplementationDetailDto("youtube.v3"),
    );

    expect(detail.implementation.implementationId).toBe("youtube.v3");
    expect(detail.implementation).not.toHaveProperty("schemaVersion");
    expect(detail.implementation.requiredCredentials).toEqual(["api_key"]);
    expect(detail.implementation.officialDocs).toEqual([
      "https://example.invalid/youtube/official-docs",
    ]);
    expect(detail.implementation.sdkSelection).toMatchObject({
      package: "youtube-sdk-candidate",
      import_name: null,
      source_url: "https://example.invalid/youtube/sdk",
      reason: "fixture-only UI contract",
    });
    expect(detail.implementation.sdkSelection).not.toHaveProperty("importName");
    expect(detail.implementation.sdkSelection).not.toHaveProperty("sourceUrl");
    expect(
      detail.assertions.every(
        (assertion) => assertion.support_status === "candidate",
      ),
    ).toBe(true);
    expect(
      detail.assertions.every(
        (assertion) =>
          assertion.constraints[0]?.constraint_type === "execution_boundary",
      ),
    ).toBe(true);
    expect(detail.assertions[0]?.evidence_refs).toEqual([
      "youtube.v3:evidence:contract",
      "youtube.v3:evidence:boundary",
    ]);
    expect(detail.evidence.map((evidence) => evidence.evidence_id)).toEqual([
      "youtube.v3:evidence:contract",
      "youtube.v3:evidence:boundary",
    ]);
    expect(detail.evidence.map((evidence) => evidence.evidence_type)).toEqual([
      "contract",
      "boundary",
    ]);
    expect(JSON.stringify(detail)).not.toContain("credential_value");
  });

  it("marks mock DTOs as fixture-only without provider or production writes", () => {
    const matrixDto = buildMockCapabilityMatrixDto();
    const implementations = buildMockCapabilityImplementations();
    const assertions = buildMockCapabilityAssertions();
    const evidence = buildMockCapabilityEvidence();

    expect(matrixDto.evidence_level).toBe("L2-fixture");
    expect(matrixDto.provider_call).toBe(false);
    expect(matrixDto.production_write_allowed).toBe(false);
    expect(assertions).toHaveLength(35);
    expect(evidence).toHaveLength(14);
    expect(
      implementations.reduce(
        (total, implementation) =>
          total + implementation.supportedEndpoints.length,
        0,
      ),
    ).toBe(38);
  });

  it("builds capability filters in the API contract order", () => {
    const result = buildCapabilityQuery({
      platform: "youtube",
      accessChannel: "official_authorized_api",
      resourceType: "conversation",
      operation: "list_enumerate",
      supportStatus: "candidate",
    });

    expect(result).toBeInstanceOf(URLSearchParams);
    expect(result.toString()).toBe(
      "platform=youtube&access_channel=official_authorized_api&resource_type=conversation&operation=list_enumerate&support_status=candidate",
    );
  });
});
