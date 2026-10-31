"use client";

import { useMemo } from "react";

/**
 * 报告正文的渲染策略：认证拉取 HTML → 注入 CSP meta → iframe srcdoc。
 *
 * 不用 `dangerouslySetInnerHTML`：报告自带完整 `<html>/<head>/<style>`，
 * 注入应用 DOM 会污染全局样式；报告里的两段脚本也会在应用源里执行。
 *
 * iframe 只给 `allow-scripts`，不给 `allow-same-origin`。文档因此是
 * opaque origin，脚本读不到父页面、Cookie 和 localStorage。CSP 由客户端
 * 在渲染时注入，不改变数据库里存储的字节和 SHA-256。
 */
export const INSIGHT_REPORT_CSP = [
  "default-src 'none'",
  "style-src 'unsafe-inline'",
  "img-src data:",
  "script-src 'unsafe-inline'",
  "connect-src 'none'",
  "font-src 'none'",
  "frame-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

export const INSIGHT_REPORT_IFRAME_SANDBOX = "allow-scripts";

/**
 * 在 `<head>` 之后插入 CSP meta。
 *
 * 导入器保证报告包含 `<head>`；如果传入的 HTML 没有 head，仍然把 meta
 * 放在开头，保持 fail-safe，而不是跳过 CSP。
 */
export function withReportCsp(html: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${INSIGHT_REPORT_CSP}">`;
  if (/<head(\s[^>]*)?>/i.test(html)) {
    return html.replace(/<head(\s[^>]*)?>/i, (match) => `${match}${meta}`);
  }
  return `${meta}${html}`;
}

export function InsightReportFrame({
  html,
  title,
}: {
  html: string;
  title: string;
}) {
  const srcDoc = useMemo(() => withReportCsp(html), [html]);

  return (
    <iframe
      className="h-[70vh] min-h-[520px] w-full rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-white lg:h-[calc(100vh-18rem)] lg:min-h-[640px]"
      data-testid="insight-report-frame"
      referrerPolicy="no-referrer"
      sandbox={INSIGHT_REPORT_IFRAME_SANDBOX}
      srcDoc={srcDoc}
      title={title}
    />
  );
}
