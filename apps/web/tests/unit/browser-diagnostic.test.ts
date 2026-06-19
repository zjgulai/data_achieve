import { describe, expect, it } from "vitest";

import {
  buildBrowserDiagnosticActionPlan,
  comparePreflightWithBrowserDiagnostic,
  parseBrowserStructureDiagnosticJson,
} from "@/lib/browser-diagnostic";
import type { ToolkitPreflightReport } from "@/types/toolkit";

const diagnosticPayload = {
  schema_version: "browser_structure_diagnostic.v1",
  generated_at: "2026-06-19T14:00:00Z",
  requested_url: "https://example.com",
  final_url: "https://example.com/",
  run_policy: {
    authorization_confirmed: true,
    execution_mode: "browser_harness_real_chrome_read_only",
    production_write: false,
    login_or_private_page_allowed: false,
    cookies_exported: false,
  },
  visible_text: {
    length: 180,
    line_count: 4,
    sample: "Example Domain",
  },
  dom_counters: {
    links: 1,
    same_origin_links: 0,
    external_links: 1,
    forms: 0,
    inputs: 0,
    buttons: 0,
    tables: 0,
    lists: 0,
    articles: 0,
    cards: 0,
    images: 0,
    scripts: 0,
    stylesheets: 0,
    json_ld_blocks: 0,
  },
  risk_flags: [],
  extraction_strategy: {
    recommended_path: "generic_web",
    fit: "high",
    confidence: 84,
    field_stability: "high",
    reasons: ["浏览器渲染后正文、链接和标题可直接读取。"],
    next_steps: ["建立 DOM 字段契约。"],
    cleaning_notes: ["清洗标题和链接。"],
  },
  network_summary: {
    resource_count: 0,
    same_origin_resources: 0,
    cross_origin_resources: 0,
    xhr_fetch_count: 0,
    script_count: 0,
    image_count: 0,
    api_candidate_count: 0,
    api_candidates: [],
    initiator_type_counts: {},
  },
  evidence: {
    screenshot_path: "tmp/outputs/browser-diagnostics/example.png",
    source: "browser-harness",
    errors: [],
  },
};

describe("parseBrowserStructureDiagnosticJson", () => {
  it("maps v1 diagnostic JSON into UI state", () => {
    const result = parseBrowserStructureDiagnosticJson(JSON.stringify(diagnosticPayload));

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }
    expect(result.diagnostic.finalUrl).toBe("https://example.com/");
    expect(result.diagnostic.runPolicy.productionWrite).toBe(false);
    expect(result.diagnostic.extractionStrategy.recommendedPath).toBe("generic_web");
    expect(result.diagnostic.domCounters.links).toBe(1);
  });

  it("rejects unsupported schema versions", () => {
    const result = parseBrowserStructureDiagnosticJson(
      JSON.stringify({ ...diagnosticPayload, schema_version: "unknown" }),
    );

    expect(result.ok).toBe(false);
    if (result.ok) {
      return;
    }
    expect(result.error).toContain("browser_structure_diagnostic.v1");
  });

  it("compares static and browser strategies", () => {
    const parsed = parseBrowserStructureDiagnosticJson(JSON.stringify(diagnosticPayload));
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) {
      return;
    }
    const report = {
      collectionStrategy: {
        recommendedPath: "browser_automation",
      },
    } as ToolkitPreflightReport;

    const comparison = comparePreflightWithBrowserDiagnostic(report, parsed.diagnostic);

    expect(comparison.pathAgreement).toBe(false);
    expect(comparison.message).toContain("真实浏览器诊断与静态预检不同");
  });

  it("builds field contract and a generic_web task draft from browser evidence", () => {
    const parsed = parseBrowserStructureDiagnosticJson(JSON.stringify(diagnosticPayload));
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) {
      return;
    }

    const plan = buildBrowserDiagnosticActionPlan(parsed.diagnostic);

    expect(plan.readiness).toBe("ready");
    expect(plan.canCreateGenericWebSource).toBe(true);
    expect(plan.primaryRecommendation.collectorType).toBe("generic_web");
    expect(plan.sourceDraft?.type).toBe("generic_web");
    expect(plan.sourceDraft?.config.fields).toContain("page_title");
    expect(plan.fieldContract.fields.map((field) => field.key)).toEqual(
      expect.arrayContaining(["page_title", "canonical_url", "visible_text"]),
    );
    expect(plan.fieldContract.cleaningRules).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ field: "canonical_url", operation: "normalize_url" }),
      ]),
    );
  });

  it("blocks generic_web task creation when browser evidence points to automation", () => {
    const browserAutomationPayload = {
      ...diagnosticPayload,
      extraction_strategy: {
        ...diagnosticPayload.extraction_strategy,
        recommended_path: "browser_automation",
        fit: "medium",
        confidence: 72,
        field_stability: "medium",
      },
      dom_counters: {
        ...diagnosticPayload.dom_counters,
        buttons: 8,
        scripts: 24,
      },
      network_summary: {
        ...diagnosticPayload.network_summary,
        xhr_fetch_count: 6,
        api_candidate_count: 2,
        api_candidates: [
          {
            url: "https://example.com/api/products",
            initiator_type: "fetch",
            same_origin: true,
            duration_ms: 124,
            transfer_size: 4096,
          },
        ],
      },
    };
    const parsed = parseBrowserStructureDiagnosticJson(JSON.stringify(browserAutomationPayload));
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) {
      return;
    }

    const plan = buildBrowserDiagnosticActionPlan(parsed.diagnostic);

    expect(plan.readiness).toBe("review");
    expect(plan.canCreateGenericWebSource).toBe(false);
    expect(plan.primaryRecommendation.toolFamily).toBe("browser_automation");
    expect(plan.blockingReasons).toContain("浏览器诊断推荐 browser_automation，不应直接创建 generic_web。");
    expect(plan.fieldContract.fields.map((field) => field.key)).toContain("api_candidate");
    expect(plan.sourceDraft).toBeNull();
  });

  it("blocks task creation when diagnostic evidence contains production write markers", () => {
    const parsed = parseBrowserStructureDiagnosticJson(
      JSON.stringify({
        ...diagnosticPayload,
        run_policy: {
          ...diagnosticPayload.run_policy,
          production_write: true,
        },
      }),
    );
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) {
      return;
    }

    const plan = buildBrowserDiagnosticActionPlan(parsed.diagnostic);

    expect(plan.readiness).toBe("blocked");
    expect(plan.canCreateGenericWebSource).toBe(false);
    expect(plan.blockingReasons).toContain("诊断证据带有生产写入标记，必须先重新执行只读诊断。");
  });
});
