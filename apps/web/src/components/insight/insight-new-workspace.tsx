"use client";

import {
  AlertTriangle,
  ArrowRight,
  Database,
  FileText,
  Inbox,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import { useEffect, useMemo, useState } from "react";

import {
  WorkbenchActionButton,
  WorkbenchEmptyState,
  WorkbenchFact,
  WorkbenchPanel,
  WorkbenchStatusPill,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import { mockApiEnabled } from "@/lib/api/client";
import {
  describeInsightError,
  listInsightAnalysisTypes,
  listInsightReports,
} from "@/lib/api/insight";
import type {
  InsightAnalysisType,
  InsightReportSummary,
} from "@/types/insight";

type ErrorContext = "types" | "list";

export function InsightNewWorkspace() {
  const [analysisTypes, setAnalysisTypes] = useState<InsightAnalysisType[]>([]);
  const [selectedTypeKey, setSelectedTypeKey] = useState<string | null>(null);
  const [reports, setReports] = useState<InsightReportSummary[]>([]);
  const [loadingTypes, setLoadingTypes] = useState(true);
  const [loadingReports, setLoadingReports] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [errorContext, setErrorContext] = useState<ErrorContext>("list");
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let mounted = true;
    setLoadingTypes(true);
    setError(null);

    listInsightAnalysisTypes()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setAnalysisTypes(items);
        setSelectedTypeKey((current) => {
          if (current && items.some((item) => item.key === current)) {
            return current;
          }
          return items[0]?.key ?? null;
        });
      })
      .catch((caught) => {
        if (!mounted) {
          return;
        }
        setAnalysisTypes([]);
        setSelectedTypeKey(null);
        setReports([]);
        setError(caught);
        setErrorContext("types");
      })
      .finally(() => {
        if (mounted) {
          setLoadingTypes(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [refreshToken]);

  useEffect(() => {
    if (!selectedTypeKey) {
      setReports([]);
      setLoadingReports(false);
      return;
    }

    let mounted = true;
    setLoadingReports(true);
    setReports([]);
    setError(null);
    setErrorContext("list");

    listInsightReports({ analysisType: selectedTypeKey })
      .then((page) => {
        if (mounted) {
          setReports(page.items);
        }
      })
      .catch((caught) => {
        if (!mounted) {
          return;
        }
        setReports([]);
        setError(caught);
        setErrorContext("list");
      })
      .finally(() => {
        if (mounted) {
          setLoadingReports(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [refreshToken, selectedTypeKey]);

  const selectedType = useMemo(
    () =>
      analysisTypes.find((item) => item.key === selectedTypeKey) ?? null,
    [analysisTypes, selectedTypeKey],
  );

  const latestReport = reports[0] ?? null;
  const totalReportCount = useMemo(
    () => analysisTypes.reduce((sum, item) => sum + item.reportCount, 0),
    [analysisTypes],
  );

  const isMock =
    mockApiEnabled ||
    analysisTypes.some((item) => item.generation.reasonCode === "mock_mode");
  const sourceNotice = buildSourceNotice(selectedType, totalReportCount, isMock);

  function handleRefresh() {
    setRefreshToken((current) => current + 1);
  }

  return (
    <div className="grid min-w-0 gap-5" data-testid="insight-new-page">
      {sourceNotice ? (
        <section
          aria-label="数据源状态"
          className="flex min-w-0 flex-col gap-2 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 sm:flex-row sm:items-start"
          data-testid="insight-source-notice"
        >
          <Database
            aria-hidden="true"
            className="mt-0.5 shrink-0 text-[var(--text-tertiary)]"
            size={17}
          />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--text-primary)]">
              {sourceNotice.title}
            </p>
            {sourceNotice.detail ? (
              <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                {sourceNotice.detail}
              </p>
            ) : null}
          </div>
        </section>
      ) : null}

      {error ? (
        <InsightErrorBanner
          context={errorContext}
          error={error}
          onRetry={handleRefresh}
        />
      ) : null}

      <div className="grid min-w-0 gap-5 lg:grid-cols-[17rem_minmax(0,1fr)]">
        <aside className="min-w-0 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 lg:self-start">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase text-[var(--action-primary)]">
                分析类型
              </p>
              <h2 className="mt-1 text-base font-semibold text-[var(--text-primary)]">
                已注册类型
              </h2>
            </div>
            <WorkbenchActionButton
              icon={RefreshCw}
              loading={loadingTypes || loadingReports}
              onClick={handleRefresh}
              tone="outline"
            >
              刷新
            </WorkbenchActionButton>
          </div>

          <div className="mt-3 flex gap-2 overflow-x-auto pb-1 lg:grid lg:overflow-visible">
            {analysisTypes.map((item) => {
              const active = item.key === selectedTypeKey;
              return (
                <button
                  aria-pressed={active}
                  className={[
                    "min-h-11 min-w-[14rem] rounded-[var(--radius-2)] border px-3 py-2 text-left transition-colors duration-[var(--duration-base)] lg:min-w-0",
                    active
                      ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                      : "border-[var(--border-subtle)] bg-[var(--surface-secondary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]",
                  ].join(" ")}
                  data-testid={`insight-analysis-type-${item.key}`}
                  key={item.key}
                  onClick={() => setSelectedTypeKey(item.key)}
                  type="button"
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold">{item.name}</span>
                    {active ? (
                      <span className="rounded-full bg-[var(--surface-primary)] px-2 py-0.5 text-[11px] font-semibold">
                        当前
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1 block text-xs leading-5">
                    {item.reportCount} 份报告
                    {active && latestReport
                      ? ` · ${formatSampleSize(latestReport)}`
                      : ""}
                  </span>
                </button>
              );
            })}

            {loadingTypes ? (
              <p
                className="rounded-[var(--radius-2)] border border-dashed border-[var(--border-strong)] px-3 py-3 text-sm text-[var(--text-secondary)]"
                role="status"
              >
                加载分析类型中
              </p>
            ) : null}

            {!loadingTypes && analysisTypes.length === 0 ? (
              <WorkbenchEmptyState
                compact
                text={
                  errorContext === "types" && error
                    ? "分析类型未加载。请重试。"
                    : "没有可用的分析类型。"
                }
              />
            ) : null}
          </div>
        </aside>

        <div className="grid min-w-0 gap-5">
          {selectedType ? (
            <WorkbenchPanel
              icon={FileText}
              label="分析类型"
              subtitle={selectedType.description}
              title={selectedType.name}
            >
              <div className="flex flex-wrap gap-2">
                <WorkbenchTag tone={sourceTagTone(latestReport)}>
                  {sourceTagLabel(latestReport)}
                </WorkbenchTag>
                <WorkbenchTag tone="muted">只读</WorkbenchTag>
                <WorkbenchTag tone="neutral">
                  {selectedType.reportCount} 份报告
                </WorkbenchTag>
              </div>
            </WorkbenchPanel>
          ) : null}

          {selectedType ? (
            <WorkbenchPanel
              action={
                <WorkbenchActionButton
                  icon={RefreshCw}
                  loading={loadingReports}
                  onClick={handleRefresh}
                  tone="outline"
                >
                  刷新
                </WorkbenchActionButton>
              }
              icon={Inbox}
              label="归档报告"
              title="已归档报告"
            >
              {loadingReports ? (
                <div role="status">
                  <WorkbenchEmptyState compact text="加载报告中" />
                </div>
              ) : null}

              {!loadingReports && reports.length === 0 && !error ? (
                <WorkbenchEmptyState
                  icon={Inbox}
                  text={
                    isMock
                      ? "测试模式不返回示例报告，避免把假数据当成真实分析。请连接真实 API，或用导入脚本写入测试报告。"
                      : "报告需要先在数据源所在环境生成，再导入工作台。页面不会实时分析。数据源未连接，暂时不能生成新报告。"
                  }
                  title={
                    isMock ? "本地测试模式没有归档报告" : "还没有归档报告"
                  }
                />
              ) : null}

              {reports.length > 0 ? (
                <div className="grid gap-3" data-testid="insight-report-list">
                  {reports.map((report) => (
                    <InsightReportCard key={report.id} report={report} />
                  ))}
                </div>
              ) : null}
            </WorkbenchPanel>
          ) : null}

          {!selectedType && !loadingTypes ? (
            error ? null : (
              <WorkbenchEmptyState
                icon={Inbox}
                text="分析类型由服务端注册表提供。请刷新，或检查服务端配置。"
                title="还没有可用的分析类型"
              />
            )
          ) : null}

          {selectedType ? (
            <WorkbenchPanel
              icon={Database}
              label="分析口径"
              title="样本与来源"
            >
              {latestReport ? (
                <InsightScopeFacts report={latestReport} />
              ) : (
                <p className="text-sm leading-6 text-[var(--text-secondary)]">
                  数据口径在报告导入时记录。导入后会显示样本量、采样方式、
                  来源环境与源表行数。当前没有可展示的报告口径。
                </p>
              )}
            </WorkbenchPanel>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function InsightReportCard({ report }: { report: InsightReportSummary }) {
  const canView = report.hasContent && report.status !== "content_missing";
  const meta = [
    report.dataScope.windowLabel,
    formatSampleSize(report),
    report.version,
  ]
    .filter((value) => value.length > 0)
    .join(" · ");

  return (
    <Link
      className="block rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-4 transition-colors duration-[var(--duration-base)] hover:border-[var(--action-primary)] focus-visible:shadow-[var(--focus-ring)]"
      data-testid="insight-report-card"
      href={`/new/${report.id}` as Route}
    >
      <div className="flex flex-wrap items-center gap-2">
        <WorkbenchStatusPill
          status={canView ? "已归档" : "正文缺失"}
          tone={canView ? "neutral" : "amber"}
        />
        <WorkbenchTag tone="muted">版本 {report.version || "未提供"}</WorkbenchTag>
      </div>
      <h3 className="mt-3 break-words text-base font-semibold text-[var(--text-primary)]">
        {report.title || "未命名报告"}
      </h3>
      {report.summary ? (
        <p className="mt-2 break-words text-sm leading-6 text-[var(--text-secondary)]">
          {report.summary}
        </p>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-[var(--text-tertiary)]">
          {meta || "数据范围未记录"}
        </p>
        <span className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--action-primary)]">
          {canView ? "打开报告" : "查看详情"}
          <ArrowRight aria-hidden="true" size={15} />
        </span>
      </div>
    </Link>
  );
}

function InsightScopeFacts({ report }: { report: InsightReportSummary }) {
  const scope = report.dataScope;
  const tableCount = scope.source.tables.length;
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      <WorkbenchFact label="样本" value={formatSampleSize(report)} />
      <WorkbenchFact label="采样" value={displayText(scope.sampling)} />
      <WorkbenchFact
        label="来源"
        value={tableCount > 0 ? `${tableCount} 张 raw 表` : "未提供"}
      />
      <WorkbenchFact label="数据截止" value={displayText(scope.windowEnd)} />
      <WorkbenchFact
        label="来源环境"
        value={displayText(scope.source.environment)}
      />
      <WorkbenchFact label="来源库" value={displayText(scope.source.database)} />
    </div>
  );
}

function InsightErrorBanner({
  context,
  error,
  onRetry,
}: {
  context: ErrorContext;
  error: unknown;
  onRetry: () => void;
}) {
  const description = describeInsightError(
    error,
    context === "types" ? "types" : "list",
  );
  const loginHref = "/login?next=%2Fnew" as Route;

  return (
    <section
      className="grid gap-3 rounded-[var(--radius-3)] border border-[var(--state-danger)] bg-[var(--surface-primary)] p-4"
      data-testid="insight-list-error"
      role="alert"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle
          aria-hidden="true"
          className="mt-0.5 shrink-0 text-[var(--state-danger)]"
          size={17}
        />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            {description.title}
          </p>
          <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
            {description.detail}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {description.kind === "auth" ? (
          <Link
            className="inline-flex h-11 items-center justify-center rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
            href={loginHref}
          >
            重新登录
          </Link>
        ) : null}
        {description.kind !== "auth" && description.kind !== "workspace" ? (
          <WorkbenchActionButton icon={RefreshCw} onClick={onRetry} tone="outline">
            重试
          </WorkbenchActionButton>
        ) : null}
      </div>
    </section>
  );
}

function buildSourceNotice(
  analysisType: InsightAnalysisType | null,
  totalReportCount: number,
  isMock: boolean,
): { title: string; detail: string } | null {
  if (!analysisType) {
    return null;
  }

  if (isMock || analysisType.generation.reasonCode === "mock_mode") {
    return {
      title: "本地测试模式不返回示例报告。",
      detail: "页面不显示虚构报告，避免把假数据当成真实分析。",
    };
  }

  if (analysisType.generation.reasonCode === "unavailable") {
    return {
      title: "数据源当前不可用，无法生成新报告。",
      detail: `当前可查看已归档的 ${totalReportCount} 份报告。`,
    };
  }

  if (analysisType.generation.reasonCode === "source_not_connected") {
    return {
      title: "数据源未连接，无法生成新报告。",
      detail: `当前可查看已归档的 ${totalReportCount} 份报告。`,
    };
  }

  if (analysisType.generation.available) {
    return {
      title: "数据源已连接。",
      detail: "当前版本仍只支持查看归档报告，生成能力尚未开放。",
    };
  }

  return {
    title: "当前无法生成新报告。",
    detail: `当前可查看已归档的 ${totalReportCount} 份报告。`,
  };
}

function sourceTagLabel(report: InsightReportSummary | null): string {
  if (!report) {
    return "数据快照";
  }
  if (report.sourceStatus === "connected") {
    return "数据源已连接";
  }
  if (report.sourceStatus === "unavailable") {
    return "数据源不可用";
  }
  return "数据快照";
}

function sourceTagTone(
  report: InsightReportSummary | null,
): "amber" | "green" | "muted" {
  if (!report) {
    return "muted";
  }
  if (report.sourceStatus === "connected") {
    return "green";
  }
  if (report.sourceStatus === "unavailable") {
    return "amber";
  }
  return "muted";
}

function formatSampleSize(report: InsightReportSummary): string {
  const size = report.dataScope.sampleSize;
  return size > 0 ? `${size} 条样本` : "样本量未记录";
}

function displayText(value: string): string {
  return value.trim().length > 0 ? value : "未提供";
}
