import { describe, expect, it } from "vitest";

import {
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
});
