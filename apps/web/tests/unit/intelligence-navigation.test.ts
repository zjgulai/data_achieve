import { describe, expect, it } from "vitest";

import {
  buildIntelligenceDetailHref,
  buildIntelligenceListHref,
  buildProjectScopedHref,
  readIntelligenceNavigationContext,
} from "@/lib/intelligence-navigation";

describe("intelligence navigation context", () => {
  it("reads a deep link and keeps the selected Evidence with its Intelligence", () => {
    const context = readIntelligenceNavigationContext(
      "?project_id=project-a&type=trend&status=new&scope=training&intelligence_id=intel-a&evidence_id=evidence-a",
    );

    expect(context).toEqual({
      evidenceId: "evidence-a",
      intelligenceId: "intel-a",
      projectId: "project-a",
      scope: "training",
      status: "new",
      type: "trend",
    });
    expect(buildIntelligenceListHref(context)).toBe(
      "/intelligence?project_id=project-a&type=trend&status=new&scope=training&intelligence_id=intel-a&evidence_id=evidence-a",
    );
    expect(buildIntelligenceDetailHref("intel-a", context)).toBe(
      "/intelligence/intel-a?project_id=project-a&type=trend&status=new&scope=training&intelligence_id=intel-a&evidence_id=evidence-a",
    );
  });

  it("round-trips list and detail without retaining orphan Evidence state", () => {
    const context = {
      evidenceId: "evidence-a",
      intelligenceId: "intel-a",
      projectId: "project a",
      scope: "all" as const,
      status: "reviewed",
      type: "risk",
    };

    expect(buildIntelligenceListHref(context)).toBe(
      "/intelligence?project_id=project+a&type=risk&status=reviewed&intelligence_id=intel-a&evidence_id=evidence-a",
    );
    expect(buildIntelligenceDetailHref("intel-a", context)).toBe(
      "/intelligence/intel-a?project_id=project+a&type=risk&status=reviewed&intelligence_id=intel-a&evidence_id=evidence-a",
    );
    expect(
      buildIntelligenceListHref({
        ...context,
        intelligenceId: null,
      }),
    ).toBe(
      "/intelligence?project_id=project+a&type=risk&status=reviewed",
    );
  });

  it("defaults invalid Scope and carries Project into downstream Evidence links", () => {
    expect(
      readIntelligenceNavigationContext(
        "?project_id=project-a&scope=unknown&intelligence_id=intel-a",
      ).scope,
    ).toBe("all");
    expect(
      buildProjectScopedHref("/tasks?run=run-a", "project-a"),
    ).toBe("/tasks?run=run-a&project_id=project-a");
    expect(
      buildProjectScopedHref("/raw-records?record=raw-a", null),
    ).toBe("/raw-records?record=raw-a");
  });
});
