"use client";

import { AlertTriangle, CheckCircle2, FileCode2, GitCompareArrows, X } from "lucide-react";
import { useMemo, useState } from "react";

import {
  comparePreflightWithBrowserDiagnostic,
  formatBrowserDiagnosticFieldStability,
  formatBrowserDiagnosticFit,
  formatBrowserDiagnosticPath,
  parseBrowserStructureDiagnosticJson,
} from "@/lib/browser-diagnostic";
import { cn } from "@/lib/utils";
import type { BrowserStructureDiagnostic } from "@/types/browser-diagnostic";
import type { ToolkitPreflightReport } from "@/types/toolkit";

type BrowserDiagnosticImportPanelProps = {
  compact?: boolean;
  preflightReport?: ToolkitPreflightReport | null;
  title?: string;
};

export function BrowserDiagnosticImportPanel({
  compact = false,
  preflightReport,
  title = "真实浏览器诊断",
}: BrowserDiagnosticImportPanelProps) {
  const [rawJson, setRawJson] = useState("");
  const [diagnostic, setDiagnostic] = useState<BrowserStructureDiagnostic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const comparison = useMemo(
    () =>
      diagnostic
        ? comparePreflightWithBrowserDiagnostic(preflightReport, diagnostic)
        : null,
    [diagnostic, preflightReport],
  );

  function importDiagnostic() {
    const parsed = parseBrowserStructureDiagnosticJson(rawJson);
    if (!parsed.ok) {
      setDiagnostic(null);
      setError(parsed.error);
      return;
    }
    setDiagnostic(parsed.diagnostic);
    setError(null);
  }

  function clearDiagnostic() {
    setRawJson("");
    setDiagnostic(null);
    setError(null);
  }

  return (
    <section
      className={cn(
        "rounded-xl border border-[#EDE6DF] bg-white p-4",
        compact ? "mt-0" : "mt-4",
      )}
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2">
            <FileCode2 size={16} className="text-[#B47767]" aria-hidden="true" />
            <h5 className="text-sm font-semibold text-[#1D1D1F]">{title}</h5>
          </div>
          <p className="text-xs leading-5 text-[#86868B]">
            browser_structure_diagnostic.v1 · JSON 证据导入 · 不触发页面采集
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {diagnostic ? (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
                diagnostic.runPolicy.productionWrite
                  ? "border-[#F0C8C0] bg-[#FFF2EF] text-[#B85F4F]"
                  : "border-[#CDE4C6] bg-[#F2FAEF] text-[#4E7C45]",
              )}
            >
              {diagnostic.runPolicy.productionWrite ? (
                <AlertTriangle size={13} aria-hidden="true" />
              ) : (
                <CheckCircle2 size={13} aria-hidden="true" />
              )}
              {diagnostic.runPolicy.productionWrite ? "存在写入标记" : "只读证据"}
            </span>
          ) : null}
          {comparison ? (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
                comparison.severity === "aligned"
                  ? "border-[#CDE4C6] bg-[#F2FAEF] text-[#4E7C45]"
                  : "border-[#F1D9A8] bg-[#FFF9E9] text-[#87611B]",
              )}
            >
              <GitCompareArrows size={13} aria-hidden="true" />
              {comparison.pathAgreement ? "路径一致" : "需要复核"}
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-3 grid gap-3">
        <label className="grid gap-2 text-xs font-semibold uppercase text-[#B47767]">
          Browser diagnostic JSON
          <textarea
            aria-label="Browser diagnostic JSON"
            className="min-h-28 resize-y rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2 font-mono text-xs leading-5 text-[#1D1D1F] outline-none transition placeholder:text-[#B9ADA8] focus:border-[#C25B6E] focus:ring-4 focus:ring-[#F6E4DF]"
            onChange={(event) => setRawJson(event.target.value)}
            placeholder="粘贴 browser_structure_diagnostic.v1 JSON"
            value={rawJson}
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-[#C25B6E] px-3 text-xs font-semibold text-white transition hover:bg-[#A24D61]"
            onClick={importDiagnostic}
            type="button"
          >
            <FileCode2 size={14} aria-hidden="true" />
            导入浏览器诊断 JSON
          </button>
          <button
            className="inline-flex h-9 items-center justify-center gap-2 rounded-xl border border-[#EDE6DF] bg-white px-3 text-xs font-semibold text-[#7A625A] transition hover:bg-[#FBF8F5]"
            onClick={clearDiagnostic}
            type="button"
          >
            <X size={14} aria-hidden="true" />
            清空
          </button>
        </div>
      </div>

      {error ? (
        <p className="mt-3 rounded-xl border border-[#F0C9C2] bg-[#FFF5F2] px-3 py-2 text-xs font-semibold text-[#A04437]">
          {error}
        </p>
      ) : null}

      {diagnostic && comparison ? (
        <BrowserDiagnosticSummary diagnostic={diagnostic} comparison={comparison} />
      ) : null}
    </section>
  );
}

function BrowserDiagnosticSummary({
  comparison,
  diagnostic,
}: {
  comparison: NonNullable<ReturnType<typeof comparePreflightWithBrowserDiagnostic>>;
  diagnostic: BrowserStructureDiagnostic;
}) {
  const strategy = diagnostic.extractionStrategy;
  return (
    <div className="mt-4 grid gap-3">
      <div
        className={cn(
          "rounded-xl border p-3 text-sm leading-5",
          comparison.severity === "aligned"
            ? "border-[#CDE4C6] bg-[#F2FAEF] text-[#2F6B3A]"
            : comparison.severity === "blocked"
              ? "border-[#F0C8C0] bg-[#FFF2EF] text-[#B85F4F]"
              : "border-[#F1D9A8] bg-[#FFF9E9] text-[#87611B]",
        )}
      >
        <p className="font-semibold">{comparison.message}</p>
        <p className="mt-1 text-xs">
          静态预检 {comparison.staticPath ? formatBrowserDiagnosticPath(comparison.staticPath) : "未对比"} · 浏览器诊断 {formatBrowserDiagnosticPath(comparison.browserPath)}
        </p>
      </div>

      <div className="grid gap-2 text-xs sm:grid-cols-2 xl:grid-cols-4">
        <DiagnosticMetric label="最终 URL" value={diagnostic.finalUrl} />
        <DiagnosticMetric
          label="推荐路径"
          value={formatBrowserDiagnosticPath(strategy.recommendedPath)}
        />
        <DiagnosticMetric
          label="适配度"
          value={`${formatBrowserDiagnosticFit(strategy.fit)} · ${strategy.confidence}%`}
        />
        <DiagnosticMetric
          label="字段稳定性"
          value={formatBrowserDiagnosticFieldStability(strategy.fieldStability)}
        />
      </div>

      <div className="grid gap-2 text-xs sm:grid-cols-2 xl:grid-cols-4">
        <DiagnosticMetric label="可见文本" value={`${diagnostic.visibleText.length} 字符`} />
        <DiagnosticMetric label="卡片" value={String(diagnostic.domCounters.cards)} />
        <DiagnosticMetric label="表单" value={String(diagnostic.domCounters.forms)} />
        <DiagnosticMetric
          label="API 候选"
          value={String(diagnostic.networkSummary.apiCandidateCount)}
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <DiagnosticList title="判断依据" items={strategy.reasons.slice(0, 4)} />
        <DiagnosticList
          title="风险标记"
          items={diagnostic.riskFlags.length > 0 ? diagnostic.riskFlags : ["未发现"]}
        />
        <DiagnosticList title="下一步" items={strategy.nextSteps.slice(0, 4)} />
      </div>

      {diagnostic.networkSummary.apiCandidates.length > 0 ? (
        <div className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
          <p className="mb-2 text-xs font-semibold uppercase text-[#B47767]">API 候选</p>
          <ul className="grid gap-1.5 text-xs leading-5 text-[#5F5757]">
            {diagnostic.networkSummary.apiCandidates.slice(0, 4).map((candidate) => (
              <li className="break-words" key={`${candidate.initiatorType}-${candidate.url}`}>
                {candidate.initiatorType || "resource"} · {candidate.url}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-2 text-xs sm:grid-cols-2">
        <DiagnosticMetric
          label="截图证据"
          value={diagnostic.evidence.screenshotPath ?? "未提供"}
        />
        <DiagnosticMetric
          label="错误"
          value={diagnostic.evidence.errors.length > 0 ? diagnostic.evidence.errors.join(" / ") : "无"}
        />
      </div>
    </div>
  );
}

function DiagnosticMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-[#EDE6DF] bg-[#FBF8F5] px-2 py-1.5">
      <p className="text-[10px] font-semibold uppercase text-[#B47767]">{label}</p>
      <p className="mt-0.5 truncate text-xs font-semibold text-[#1D1D1F]">{value}</p>
    </div>
  );
}

function DiagnosticList({ items, title }: { items: string[]; title: string }) {
  return (
    <div className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
      <p className="mb-2 text-xs font-semibold uppercase text-[#B47767]">{title}</p>
      <ul className="grid gap-1.5 text-xs leading-5 text-[#5F5757]">
        {items.map((item) => (
          <li className="break-words" key={item}>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
