import { describe, expect, it } from "vitest";

import {
  INSIGHT_REPORT_CSP,
  INSIGHT_REPORT_IFRAME_SANDBOX,
  withReportCsp,
} from "@/components/insight/insight-report-frame";

describe("insight report frame", () => {
  it("injects the CSP meta directly after the head tag", () => {
    const html =
      '<!DOCTYPE html><html lang="zh-CN"><head><title>报告</title></head><body><p>正文</p></body></html>';
    const result = withReportCsp(html);

    expect(result).toContain(
      '<head><meta http-equiv="Content-Security-Policy"',
    );
    expect(result).toContain("<p>正文</p>");
    expect(result.indexOf("Content-Security-Policy")).toBeLessThan(
      result.indexOf("</head>"),
    );
  });

  it("keeps head attributes and report bytes before and after the head tag", () => {
    const html =
      '<html><head data-report="v1"><style>body{color:#222}</style></head><body>ok</body></html>';
    const result = withReportCsp(html);

    expect(result).toContain('<head data-report="v1"><meta');
    expect(result).toContain("<style>body{color:#222}</style>");
    expect(result.replace(/<meta http-equiv="Content-Security-Policy"[^>]*>/, "")).toBe(
      html,
    );
  });

  it("falls back to prepending the meta when the document has no head", () => {
    const result = withReportCsp("<p>fragment</p>");

    expect(result.startsWith('<meta http-equiv="Content-Security-Policy"')).toBe(
      true,
    );
    expect(result.endsWith("<p>fragment</p>")).toBe(true);
  });

  it("uses a strict CSP that blocks external requests and forms", () => {
    expect(INSIGHT_REPORT_CSP).toContain("default-src 'none'");
    expect(INSIGHT_REPORT_CSP).toContain("style-src 'unsafe-inline'");
    expect(INSIGHT_REPORT_CSP).toContain("img-src data:");
    expect(INSIGHT_REPORT_CSP).toContain("script-src 'unsafe-inline'");
    expect(INSIGHT_REPORT_CSP).toContain("connect-src 'none'");
    expect(INSIGHT_REPORT_CSP).toContain("base-uri 'none'");
    expect(INSIGHT_REPORT_CSP).toContain("form-action 'none'");
    expect(INSIGHT_REPORT_CSP).not.toContain("http:");
    expect(INSIGHT_REPORT_CSP).not.toContain("https:");
  });

  it("sandboxes report scripts without granting same-origin access", () => {
    expect(INSIGHT_REPORT_IFRAME_SANDBOX).toBe("allow-scripts");
    expect(INSIGHT_REPORT_IFRAME_SANDBOX).not.toContain("allow-same-origin");
    expect(INSIGHT_REPORT_IFRAME_SANDBOX).not.toContain("allow-top-navigation");
    expect(INSIGHT_REPORT_IFRAME_SANDBOX).not.toContain("allow-forms");
    expect(INSIGHT_REPORT_IFRAME_SANDBOX).not.toContain("allow-popups");
  });
});
