"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Database,
  FileCode2,
  GitCompareArrows,
  Loader2,
  Search,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  buildBrowserDiagnosticActionPlan,
  comparePreflightWithBrowserDiagnostic,
  formatBrowserDiagnosticFieldStability,
  formatBrowserDiagnosticFit,
  formatBrowserDiagnosticPath,
  parseBrowserStructureDiagnosticJson,
} from "@/lib/browser-diagnostic";
import { cn } from "@/lib/utils";
import type {
  BrowserDiagnosticActionPlan,
  BrowserDiagnosticFieldContractEdit,
  BrowserDiagnosticFieldContractField,
  BrowserStructureDiagnostic,
} from "@/types/browser-diagnostic";
import type { ToolkitPreflightReport } from "@/types/toolkit";

type BrowserDiagnosticImportPanelProps = {
  browserAutomationPlanSaveDisabledReason?: string | null;
  browserAutomationPlanSaveMessage?: string | null;
  browserAutomationPlanSaving?: boolean;
  compact?: boolean;
  onActionPlanChange?: (actionPlan: BrowserDiagnosticActionPlan | null) => void;
  onDiagnosticChange?: (diagnostic: BrowserStructureDiagnostic | null) => void;
  onSaveBrowserAutomationPlan?: (
    actionPlan: BrowserDiagnosticActionPlan,
    diagnostic: BrowserStructureDiagnostic,
  ) => Promise<void> | void;
  preflightReport?: ToolkitPreflightReport | null;
  title?: string;
};

export function BrowserDiagnosticImportPanel({
  browserAutomationPlanSaveDisabledReason,
  browserAutomationPlanSaveMessage,
  browserAutomationPlanSaving = false,
  compact = false,
  onActionPlanChange,
  onDiagnosticChange,
  onSaveBrowserAutomationPlan,
  preflightReport,
  title = "真实浏览器诊断",
}: BrowserDiagnosticImportPanelProps) {
  const [rawJson, setRawJson] = useState("");
  const [diagnostic, setDiagnostic] = useState<BrowserStructureDiagnostic | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldEdits, setFieldEdits] = useState<BrowserDiagnosticFieldContractEdit[]>([]);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const comparison = useMemo(
    () =>
      diagnostic
        ? comparePreflightWithBrowserDiagnostic(preflightReport, diagnostic)
        : null,
    [diagnostic, preflightReport],
  );
  const actionPlan = useMemo(
    () =>
      diagnostic
        ? buildBrowserDiagnosticActionPlan(diagnostic, {
            fieldEdits,
            savedAt,
          })
        : null,
    [diagnostic, fieldEdits, savedAt],
  );

  useEffect(() => {
    onActionPlanChange?.(actionPlan);
  }, [actionPlan, onActionPlanChange]);

  function importDiagnostic() {
    const parsed = parseBrowserStructureDiagnosticJson(rawJson);
    if (!parsed.ok) {
      setDiagnostic(null);
      setFieldEdits([]);
      setSavedAt(null);
      setError(parsed.error);
      return;
    }
    setDiagnostic(parsed.diagnostic);
    setFieldEdits([]);
    setSavedAt(null);
    onDiagnosticChange?.(parsed.diagnostic);
    setError(null);
  }

  function clearDiagnostic() {
    setRawJson("");
    setDiagnostic(null);
    setFieldEdits([]);
    setSavedAt(null);
    onDiagnosticChange?.(null);
    setError(null);
  }

  function updateFieldEdit(key: string, patch: Omit<BrowserDiagnosticFieldContractEdit, "key">) {
    setFieldEdits((current) => {
      const existing = current.find((edit) => edit.key === key);
      if (!existing) {
        return [...current, { key, ...patch }];
      }
      return current.map((edit) => (edit.key === key ? { ...edit, ...patch } : edit));
    });
  }

  function saveFieldContractDraft() {
    setSavedAt(new Date().toISOString());
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

      {diagnostic && comparison && actionPlan ? (
        <BrowserDiagnosticSummary
          actionPlan={actionPlan}
          browserAutomationPlanSaveDisabledReason={
            browserAutomationPlanSaveDisabledReason
          }
          browserAutomationPlanSaveMessage={browserAutomationPlanSaveMessage}
          browserAutomationPlanSaving={browserAutomationPlanSaving}
          comparison={comparison}
          diagnostic={diagnostic}
          onFieldEdit={updateFieldEdit}
          onSaveFieldContract={saveFieldContractDraft}
          onSaveBrowserAutomationPlan={onSaveBrowserAutomationPlan}
        />
      ) : null}
    </section>
  );
}

function BrowserDiagnosticSummary({
  actionPlan,
  browserAutomationPlanSaveDisabledReason,
  browserAutomationPlanSaveMessage,
  browserAutomationPlanSaving,
  comparison,
  diagnostic,
  onFieldEdit,
  onSaveBrowserAutomationPlan,
  onSaveFieldContract,
}: {
  actionPlan: BrowserDiagnosticActionPlan;
  browserAutomationPlanSaveDisabledReason?: string | null;
  browserAutomationPlanSaveMessage?: string | null;
  browserAutomationPlanSaving: boolean;
  comparison: NonNullable<ReturnType<typeof comparePreflightWithBrowserDiagnostic>>;
  diagnostic: BrowserStructureDiagnostic;
  onFieldEdit: (key: string, patch: Omit<BrowserDiagnosticFieldContractEdit, "key">) => void;
  onSaveBrowserAutomationPlan?: (
    actionPlan: BrowserDiagnosticActionPlan,
    diagnostic: BrowserStructureDiagnostic,
  ) => Promise<void> | void;
  onSaveFieldContract: () => void;
}) {
  const strategy = diagnostic.extractionStrategy;
  const selectedFieldCount = actionPlan.fieldContract.fields.filter((field) => field.selected).length;
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

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
          <div className="mb-2 flex items-center gap-2">
            <ClipboardList size={14} className="text-[#B47767]" aria-hidden="true" />
            <p className="text-xs font-semibold uppercase text-[#B47767]">字段契约草案</p>
          </div>
          <p className="mb-2 text-sm font-semibold text-[#1D1D1F]">
            {actionPlan.fieldContract.title}
          </p>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#7A625A]">
              已选择 {selectedFieldCount} 个字段
            </span>
            <button
              className="inline-flex h-8 items-center justify-center rounded-lg bg-[#C25B6E] px-3 text-xs font-semibold text-white transition hover:bg-[#A24D61]"
              onClick={onSaveFieldContract}
              type="button"
            >
              保存字段契约草稿
            </button>
          </div>
          {actionPlan.fieldContract.savedAt ? (
            <p className="mb-2 rounded-lg border border-[#CDE4C6] bg-[#F2FAEF] px-2.5 py-1.5 text-xs font-semibold text-[#4E7C45]">
              字段契约已保存
            </p>
          ) : null}
          <div className="grid gap-2">
            {actionPlan.fieldContract.fields.slice(0, 6).map((field) => (
              <FieldContractEditor
                field={field}
                key={field.key}
                onFieldEdit={onFieldEdit}
              />
            ))}
          </div>
        </div>

        <div className="grid gap-3">
          <div className="rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] p-3">
            <div className="mb-2 flex items-center gap-2">
              <Search size={14} className="text-[#B47767]" aria-hidden="true" />
              <p className="text-xs font-semibold uppercase text-[#B47767]">采集工具推荐</p>
            </div>
            <div className="rounded-lg border border-[#EDE6DF] bg-white px-2.5 py-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold text-[#1D1D1F]">
                    {actionPlan.primaryRecommendation.toolLabel}
                  </p>
                  <p className="mt-1 text-xs font-semibold uppercase text-[#B47767]">
                    {actionPlan.primaryRecommendation.fit} · {actionPlan.primaryRecommendation.collectorType}
                  </p>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                    actionPlan.readiness === "ready"
                      ? "bg-[#F2FAEF] text-[#4E7C45]"
                      : actionPlan.readiness === "blocked"
                        ? "bg-[#FFF2EF] text-[#B85F4F]"
                        : "bg-[#FFF9E9] text-[#87611B]",
                  )}
                >
                  {actionPlan.canCreateGenericWebSource ? "可创建 generic_web 草稿" : "创建前复核"}
                </span>
              </div>
              <p className="mt-2 text-xs leading-5 text-[#5F5757]">
                {actionPlan.primaryRecommendation.reason}
              </p>
            </div>
            {actionPlan.blockingReasons.length > 0 ? (
              <DiagnosticList title="创建前阻断" items={actionPlan.blockingReasons} />
            ) : null}
          </div>

          {actionPlan.sourceDraft ? (
            <div className="rounded-xl border border-[#CDE4C6] bg-[#F2FAEF] p-3">
              <div className="mb-2 flex items-center gap-2">
                <Database size={14} className="text-[#4E7C45]" aria-hidden="true" />
                <p className="text-xs font-semibold uppercase text-[#4E7C45]">采集源草稿</p>
              </div>
              <p className="text-sm font-semibold text-[#2F6B3A]">
                {actionPlan.sourceDraft.suggestedName}
              </p>
              <p className="mt-1 text-xs leading-5 text-[#4F7F56]">
                {actionPlan.sourceDraft.type} · 字段 {actionPlan.sourceDraft.config.fields.join(", ")}
              </p>
            </div>
          ) : null}
          {actionPlan.browserAutomationDraft ? (
            <div className="rounded-xl border border-[#F1D9A8] bg-[#FFF9E9] p-3">
              <div className="mb-2 flex items-center gap-2">
                <Database size={14} className="text-[#87611B]" aria-hidden="true" />
                <p className="text-xs font-semibold uppercase text-[#87611B]">浏览器自动化任务草稿</p>
              </div>
              <p className="text-sm font-semibold text-[#5F4618]">
                {actionPlan.browserAutomationDraft.suggestedName}
              </p>
              <p className="mt-1 text-xs leading-5 text-[#87611B]">
                {actionPlan.browserAutomationDraft.runner} · 字段{" "}
                {actionPlan.browserAutomationDraft.config.field_contract.fields
                  .map((field) => field.key)
                  .join(", ")}
              </p>
              <DiagnosticList
                items={actionPlan.browserAutomationDraft.guardrails.slice(0, 3)}
                title="执行边界"
              />
              {onSaveBrowserAutomationPlan ? (
                <div className="mt-3 grid gap-2">
                  <button
                    className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-[#87611B] px-3 text-xs font-semibold text-white transition hover:bg-[#6F5018] disabled:cursor-not-allowed disabled:bg-[#D6C08C]"
                    disabled={
                      browserAutomationPlanSaving ||
                      Boolean(browserAutomationPlanSaveDisabledReason)
                    }
                    onClick={() => void onSaveBrowserAutomationPlan(actionPlan, diagnostic)}
                    type="button"
                  >
                    {browserAutomationPlanSaving ? (
                      <Loader2 className="animate-spin" size={14} aria-hidden="true" />
                    ) : (
                      <Database size={14} aria-hidden="true" />
                    )}
                    保存只读自动化方案
                  </button>
                  {browserAutomationPlanSaveDisabledReason ? (
                    <p className="text-xs leading-5 text-[#9B6A1D]">
                      {browserAutomationPlanSaveDisabledReason}
                    </p>
                  ) : null}
                  {browserAutomationPlanSaveMessage ? (
                    <p className="rounded-lg border border-[#CDE4C6] bg-[#F2FAEF] px-2.5 py-1.5 text-xs font-semibold text-[#4E7C45]">
                      {browserAutomationPlanSaveMessage}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function FieldContractEditor({
  field,
  onFieldEdit,
}: {
  field: BrowserDiagnosticFieldContractField;
  onFieldEdit: (key: string, patch: Omit<BrowserDiagnosticFieldContractEdit, "key">) => void;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-white px-2.5 py-2",
        field.selected ? "border-[#EDE6DF]" : "border-[#F0C8C0] opacity-80",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="inline-flex items-center gap-2 text-xs font-semibold text-[#1D1D1F]">
          <input
            aria-label={`选择字段 ${field.label}`}
            checked={field.selected}
            className="h-4 w-4 accent-[#C25B6E]"
            onChange={(event) => onFieldEdit(field.key, { selected: event.target.checked })}
            type="checkbox"
          />
          {field.label}
        </label>
        <span className="rounded-full bg-[#FFF0EA] px-2 py-0.5 text-[10px] font-semibold text-[#9E5C4D]">
          {field.required ? "必填" : "可选"} · {formatBrowserDiagnosticFieldStability(field.stability)}
        </span>
      </div>
      <p className="mt-1 truncate text-xs text-[#5F5757]">{field.valueSample}</p>
      <label className="mt-2 grid gap-1 text-[10px] font-semibold uppercase text-[#B47767]">
        Selector
        <input
          aria-label={`Selector hint for ${field.key}`}
          className="h-8 rounded-lg border border-[#EDE6DF] bg-[#FBF8F5] px-2 text-xs normal-case text-[#1D1D1F] outline-none focus:border-[#C25B6E]"
          onChange={(event) => onFieldEdit(field.key, { selectorHint: event.target.value })}
          value={field.selectorHint}
        />
      </label>
      <p className="mt-1 text-[10px] font-semibold uppercase text-[#B47767]">
        {field.source}
      </p>
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
