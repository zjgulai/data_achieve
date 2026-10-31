"use client";

import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Copy,
  Database,
  Download,
  FileText,
  Inbox,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import { useEffect, useState, type ReactNode } from "react";

import {
  WorkbenchActionButton,
  WorkbenchEmptyState,
  WorkbenchFact,
  WorkbenchPanel,
  WorkbenchStatusPill,
  WorkbenchTag,
} from "@/components/common/workbench-ui";
import type { WorkbenchStatusTone } from "@/components/common/workbench-ui";
import { InsightReportFrame } from "@/components/insight/insight-report-frame";
import { mockApiEnabled } from "@/lib/api/client";
import {
  describeInsightError,
  downloadInsightReportContent,
  getInsightReport,
  getInsightReportContent,
  insightAnalysisTypeLabel,
  insightReportDownloadFilename,
} from "@/lib/api/insight";
import type { InsightReportDetail } from "@/types/insight";

type CopyState = "idle" | "copied" | "failed";

export function InsightReportDetailWorkspace({
  reportId,
}: {
  reportId: string;
}) {
  const [report, setReport] = useState<InsightReportDetail | null>(null);
  const [loading, setLoading] = useState(!mockApiEnabled);
  const [error, setError] = useState<unknown>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const [content, setContent] = useState<string | null>(null);
  const [contentLoading, setContentLoading] = useState(false);
  const [contentError, setContentError] = useState<unknown>(null);
  const [contentReloadToken, setContentReloadToken] = useState(0);

  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<CopyState>("idle");

  const canRenderContent = Boolean(
    report && report.hasContent && report.status !== "content_missing",
  );
  const contentReportId = report?.id ?? null;
  const contentSha256 = report?.contentSha256 ?? null;

  useEffect(() => {
    if (mockApiEnabled) {
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);
    setReport(null);
    setContent(null);
    setContentError(null);

    getInsightReport(reportId)
      .then((item) => {
        if (mounted) {
          setReport(item);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught);
        }
      })
      .finally(() => {
        if (mounted) {
          setLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [reloadToken, reportId]);

  useEffect(() => {
    if (mockApiEnabled || !contentReportId || !canRenderContent) {
      setContent(null);
      setContentLoading(false);
      return;
    }

    let mounted = true;
    setContentLoading(true);
    setContentError(null);
    setContent(null);

    getInsightReportContent(contentReportId)
      .then((html) => {
        if (mounted) {
          setContent(html);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setContentError(caught);
        }
      })
      .finally(() => {
        if (mounted) {
          setContentLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [canRenderContent, contentReloadToken, contentReportId, contentSha256]);

  async function handleDownload() {
    if (!report) {
      return;
    }
    setDownloading(true);
    setDownloadError(null);
    try {
      await downloadInsightReportContent(
        report.id,
        insightReportDownloadFilename(report),
      );
    } catch (caught) {
      setDownloadError(downloadErrorMessage(caught));
    } finally {
      setDownloading(false);
    }
  }

  async function handleCopyReportId() {
    const value = report?.id ?? reportId;
    const copied = await copyTextToClipboard(value);
    setCopyState(copied ? "copied" : "failed");
    if (copied) {
      window.setTimeout(() => setCopyState("idle"), 2000);
    }
  }

  if (mockApiEnabled) {
    return (
      <div className="grid min-w-0 gap-5" data-testid="insight-report-detail">
        <BackLink />
        <WorkbenchEmptyState
          icon={Inbox}
          text="测试模式不返回示例报告，避免把假数据当成真实分析。请连接真实 API，或用导入脚本写入测试报告。"
          title="本地测试模式没有归档报告"
        />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="grid min-w-0 gap-5" data-testid="insight-report-detail">
        <BackLink />
        <p
          className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          role="status"
        >
          加载报告中
        </p>
      </div>
    );
  }

  if (error || !report) {
    const description = describeInsightError(error, "detail");
    const canRetry =
      description.kind !== "auth" &&
      description.kind !== "workspace" &&
      description.kind !== "not_found";

    return (
      <div className="grid min-w-0 gap-5" data-testid="insight-report-detail">
        <BackLink />
        <InsightProblemPanel
          detail={description.detail}
          title={description.title}
        >
          {description.kind === "auth" ? (
            <InsightLinkButton
              href={buildLoginHref(`/new/${reportId}`)}
              icon={ArrowLeft}
            >
              重新登录
            </InsightLinkButton>
          ) : null}
          {canRetry ? (
            <WorkbenchActionButton
              icon={RefreshCw}
              onClick={() => setReloadToken((current) => current + 1)}
              tone="outline"
            >
              重试
            </WorkbenchActionButton>
          ) : null}
          <InsightLinkButton href="/new" icon={ArrowLeft}>
            返回列表
          </InsightLinkButton>
        </InsightProblemPanel>
      </div>
    );
  }

  const contentFailure = contentError
    ? buildContentFailure(contentError)
    : null;

  // 状态要跟着正文的真实结果走。元数据说"有正文"只代表入库过一行，不代表
  // 这次能读出来：正文可能在端点返回 409（缺失 / 哈希不符）。在结果出来前
  // 不能先报"可查看"，否则点击前的承诺会被点击后的错误推翻。
  const contentStatusLabel = !canRenderContent
    ? "正文缺失"
    : contentFailure
      ? "正文不可用"
      : content
        ? "已校验"
        : "校验中";
  const contentStatusTone: WorkbenchStatusTone = !canRenderContent
    ? "amber"
    : contentFailure
      ? "red"
      : content
        ? "green"
        : "neutral";

  return (
    <div className="grid min-w-0 gap-5" data-testid="insight-report-detail">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <BackLink />
        <div className="flex flex-wrap items-center justify-end gap-3">
          {downloadError ? (
            <p className="text-xs font-semibold text-[var(--state-danger)]" role="alert">
              {downloadError}
            </p>
          ) : null}
          {canRenderContent ? (
            <WorkbenchActionButton
              icon={Download}
              loading={downloading}
              onClick={() => void handleDownload()}
              tone="outline"
            >
              下载 HTML
            </WorkbenchActionButton>
          ) : null}
        </div>
      </div>

      <section className="grid gap-4 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 sm:p-5">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-[var(--action-primary)]">
            {insightAnalysisTypeLabel(report.analysisType)}
          </p>
          <h2 className="mt-1 break-words text-xl font-semibold leading-8 text-[var(--text-primary)]">
            {report.title || "未命名报告"}
          </h2>
          {report.summary ? (
            <p className="mt-2 break-words text-sm leading-6 text-[var(--text-secondary)]">
              {report.summary}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <WorkbenchTag tone={sourceTagTone(report)}>
            {sourceTagLabel(report)}
          </WorkbenchTag>
          <WorkbenchStatusPill
            status={contentStatusLabel}
            tone={contentStatusTone}
          />
          <WorkbenchTag tone="muted">
            版本 {report.version || "未提供"}
          </WorkbenchTag>
        </div>
      </section>

      <InsightSourceNotice report={report} />
      <InsightMetaFacts report={report} />

      <WorkbenchPanel icon={FileText} label="报告正文" title="归档正文">
        {!canRenderContent ? (
          <InsightProblemPanel
            detail="报告的元数据已入库，正文记录不存在或未写入。系统已停止展示这份报告。"
            meta={`报告 ID：${report.id} · 版本：${report.version || "未提供"}`}
            title="报告正文未导入"
          >
            <WorkbenchActionButton
              icon={RefreshCw}
              onClick={() => setReloadToken((current) => current + 1)}
            >
              重新加载
            </WorkbenchActionButton>
            <CopyReportIdButton
              copyState={copyState}
              onClick={() => void handleCopyReportId()}
            />
            <InsightLinkButton href="/new" icon={ArrowLeft}>
              返回列表
            </InsightLinkButton>
          </InsightProblemPanel>
        ) : contentLoading ? (
          <p className="text-sm text-[var(--text-secondary)]" role="status">
            正在加载报告正文…
          </p>
        ) : contentFailure ? (
          <InsightProblemPanel
            detail={contentFailure.detail}
            meta={`报告 ID：${report.id} · 版本：${report.version || "未提供"}`}
            title={contentFailure.title}
          >
            {contentFailure.login ? (
              <InsightLinkButton
                href={buildLoginHref(`/new/${report.id}`)}
                icon={ArrowLeft}
              >
                重新登录
              </InsightLinkButton>
            ) : null}
            {contentFailure.canRetry ? (
              <WorkbenchActionButton
                icon={RefreshCw}
                onClick={() => setContentReloadToken((current) => current + 1)}
              >
                重新加载
              </WorkbenchActionButton>
            ) : null}
            <CopyReportIdButton
              copyState={copyState}
              onClick={() => void handleCopyReportId()}
            />
            <InsightLinkButton href="/new" icon={ArrowLeft}>
              返回列表
            </InsightLinkButton>
          </InsightProblemPanel>
        ) : content ? (
          <InsightReportFrame
            html={content}
            title={`报告正文：${report.title || report.id}`}
          />
        ) : (
          <InsightProblemPanel
            detail="正文请求没有返回内容。系统已停止展示，避免显示半份报告。"
            meta={`报告 ID：${report.id} · 版本：${report.version || "未提供"}`}
            title="报告正文未加载"
          >
            <WorkbenchActionButton
              icon={RefreshCw}
              onClick={() => setContentReloadToken((current) => current + 1)}
            >
              重新加载
            </WorkbenchActionButton>
            <CopyReportIdButton
              copyState={copyState}
              onClick={() => void handleCopyReportId()}
            />
            <InsightLinkButton href="/new" icon={ArrowLeft}>
              返回列表
            </InsightLinkButton>
          </InsightProblemPanel>
        )}
      </WorkbenchPanel>
    </div>
  );
}

function BackLink() {
  return (
    <InsightLinkButton href="/new" icon={ArrowLeft}>
      返回新建洞察
    </InsightLinkButton>
  );
}

function InsightSourceNotice({ report }: { report: InsightReportDetail }) {
  const title =
    report.sourceStatus === "connected"
      ? "数据源已连接。"
      : report.sourceStatus === "unavailable"
        ? "数据源当前不可用。"
        : "数据源未连接，无法生成新报告。";
  const detail = `当前展示 ${report.version || "已归档"} 归档的版本。查看正文不依赖数据源。`;

  return (
    <section className="flex min-w-0 flex-col gap-2 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 sm:flex-row sm:items-start">
      <Database
        aria-hidden="true"
        className="mt-0.5 shrink-0 text-[var(--text-tertiary)]"
        size={17}
      />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[var(--text-primary)]">{title}</p>
        <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
          {detail}
        </p>
        {report.sourceNote ? (
          <p className="mt-1 break-words text-xs leading-5 text-[var(--text-tertiary)]">
            {report.sourceNote}
          </p>
        ) : null}
      </div>
    </section>
  );
}

function InsightMetaFacts({ report }: { report: InsightReportDetail }) {
  const scope = report.dataScope;
  const tables = scope.source.tables;
  const sourceEnvironment = [scope.source.environment, scope.source.database]
    .filter((value) => value.trim().length > 0)
    .join(" / ");

  return (
    <div className="grid gap-2">
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        <WorkbenchFact
          label="数据窗口"
          value={formatWindow(scope.windowLabel, scope.windowEnd)}
        />
        <WorkbenchFact label="样本" value={formatSampleSize(report)} />
        <WorkbenchFact label="采样" value={displayText(scope.sampling)} />
        <WorkbenchFact
          label="来源"
          value={tables.length > 0 ? `${tables.length} 张 raw 表` : "未提供"}
        />
        <WorkbenchFact
          label="来源环境"
          value={sourceEnvironment.length > 0 ? sourceEnvironment : "未提供"}
        />
        <WorkbenchFact
          label="生成"
          value={formatIsoDate(report.generatedAt)}
        />
        <WorkbenchFact label="导入" value={formatIsoDate(report.importedAt)} />
        <div title={report.contentSha256 ?? undefined}>
          <WorkbenchFact
            label="正文"
            value={
              report.hasContent
                ? `${formatBytes(report.contentBytes)} 字节 · SHA-256 ${formatShortHash(report.contentSha256)}`
                : "正文缺失"
            }
          />
        </div>
        <WorkbenchFact
          label="版本"
          value={displayText(report.version)}
        />
      </div>

      {tables.length > 0 ? (
        <details className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2">
          <summary className="cursor-pointer text-sm font-semibold text-[var(--text-primary)]">
            源表行数（{tables.length} 张）
          </summary>
          <ul className="mt-2 grid gap-1">
            {tables.map((table) => (
              <li
                className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-1)] bg-[var(--surface-primary)] px-2 py-1 text-xs"
                key={`${table.schema}.${table.name}`}
              >
                <span className="break-all font-medium text-[var(--text-secondary)]">
                  {table.schema ? `${table.schema}.${table.name}` : table.name}
                </span>
                <span className="font-semibold text-[var(--text-primary)]">
                  {formatNumber(table.rows)} 行
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function InsightProblemPanel({
  children,
  detail,
  meta,
  title,
}: {
  children?: ReactNode;
  detail: string;
  meta?: string;
  title: string;
}) {
  return (
    <section
      className="grid gap-3 rounded-[var(--radius-3)] border border-[var(--state-danger)] bg-[var(--surface-primary)] p-4"
      role="alert"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle
          aria-hidden="true"
          className="mt-0.5 shrink-0 text-[var(--state-danger)]"
          size={17}
        />
        <div className="min-w-0">
          <h3 className="break-words text-sm font-semibold text-[var(--text-primary)]">
            {title}
          </h3>
          <p className="mt-1 break-words text-sm leading-6 text-[var(--text-secondary)]">
            {detail}
          </p>
          {meta ? (
            <p className="mt-2 break-all text-xs leading-5 text-[var(--text-tertiary)]">
              {meta}
            </p>
          ) : null}
        </div>
      </div>
      {children ? (
        <div className="flex flex-wrap items-center gap-2">{children}</div>
      ) : null}
    </section>
  );
}

function CopyReportIdButton({
  copyState,
  onClick,
}: {
  copyState: CopyState;
  onClick: () => void;
}) {
  const label =
    copyState === "copied"
      ? "已复制"
      : copyState === "failed"
        ? "复制失败"
        : "复制报告 ID";
  return (
    <WorkbenchActionButton
      icon={copyState === "copied" ? Check : Copy}
      onClick={onClick}
      tone="outline"
    >
      {label}
    </WorkbenchActionButton>
  );
}

function InsightLinkButton({
  children,
  href,
  icon: Icon,
}: {
  children: ReactNode;
  href: Route;
  icon?: typeof ArrowLeft;
}) {
  return (
    <Link
      className="inline-flex h-11 items-center justify-center gap-2 rounded-[var(--radius-2)] border border-[var(--border-strong)] bg-[var(--surface-primary)] px-4 text-sm font-semibold text-[var(--text-secondary)] transition-colors duration-[var(--duration-base)] hover:border-[var(--action-primary)] hover:text-[var(--action-primary)]"
      href={href}
    >
      {Icon ? <Icon aria-hidden="true" size={15} /> : null}
      {children}
    </Link>
  );
}

function buildContentFailure(error: unknown): {
  title: string;
  detail: string;
  canRetry: boolean;
  login: boolean;
} {
  const description = describeInsightError(error, "content");

  if (description.kind === "content_missing") {
    return {
      title: "报告正文未导入",
      detail: "报告的元数据已入库，正文记录不存在或未写入。系统已停止展示这份报告。",
      canRetry: true,
      login: false,
    };
  }

  if (description.kind === "integrity_failed") {
    return {
      title: "报告正文校验失败",
      detail: "正文的 SHA-256 与入库记录不一致。系统已停止展示，避免显示被改动的报告。",
      canRetry: true,
      login: false,
    };
  }

  return {
    title: description.title,
    detail: description.detail,
    canRetry:
      description.kind === "unavailable" || description.kind === "validation",
    login: description.kind === "auth",
  };
}

function downloadErrorMessage(error: unknown): string {
  const description = describeInsightError(error, "content");
  if (description.kind === "content_missing") {
    return "下载失败：报告正文未导入。";
  }
  if (description.kind === "integrity_failed") {
    return "下载失败：报告正文校验失败。";
  }
  if (description.kind === "auth") {
    return "登录已过期，请重新登录。";
  }
  if (description.kind === "workspace") {
    return "当前工作区不可用。";
  }
  if (description.kind === "not_found") {
    return "报告不存在或已被移除。";
  }
  return "下载失败：网络或服务异常，请稍后重试。";
}

function buildLoginHref(next: string): Route {
  return `/login?next=${encodeURIComponent(next)}` as Route;
}

function sourceTagLabel(report: InsightReportDetail): string {
  if (report.sourceStatus === "connected") {
    return "数据源已连接";
  }
  if (report.sourceStatus === "unavailable") {
    return "数据源不可用";
  }
  return "数据快照";
}

function sourceTagTone(
  report: InsightReportDetail,
): "amber" | "green" | "muted" {
  if (report.sourceStatus === "connected") {
    return "green";
  }
  if (report.sourceStatus === "unavailable") {
    return "amber";
  }
  return "muted";
}

function formatWindow(windowLabel: string, windowEnd: string): string {
  if (windowLabel && windowEnd) {
    return `${windowLabel}（截至 ${windowEnd}）`;
  }
  if (windowLabel) {
    return windowLabel;
  }
  return displayText(windowEnd);
}

function formatSampleSize(report: InsightReportDetail): string {
  return report.dataScope.sampleSize > 0
    ? `${report.dataScope.sampleSize} 条`
    : "未提供";
}

function displayText(value: string): string {
  return value.trim().length > 0 ? value : "未提供";
}

function formatIsoDate(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value);
  return match?.[1] ?? "未记录";
}

function formatBytes(value: number | null): string {
  if (value === null) {
    return "未记录";
  }
  return formatNumber(value);
}

function formatNumber(value: number): string {
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function formatShortHash(value: string | null): string {
  return value ? `${value.slice(0, 8)}…` : "未记录";
}

async function copyTextToClipboard(value: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // 浏览器拒绝 Clipboard API 时回退到旧方案。
    }
  }

  try {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  } catch {
    return false;
  }
}
