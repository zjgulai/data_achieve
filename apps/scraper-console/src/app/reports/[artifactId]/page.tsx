"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  FileText,
  Printer,
  RefreshCw,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import {
  fetchReportById,
  fetchReportContract,
  isContractGapResult,
  type Claim,
  type Evidence,
  type ReportContract,
} from "@/lib/api/reports";
import {
  CLAIM_STATUSES,
  EVIDENCE_GRADE_LABELS,
  EVIDENCE_GRADE_TONES,
  claimDistribution,
  claimDistributionText,
  claimStatusDisplay,
  contractAbsenceText,
  contractEndpointPath,
  contractGapView,
  contractRenderBranch,
  evidenceRoleLabel,
  findForbiddenWords,
  formatPeriod,
  formatTimestamp,
  gateLine,
  gateStatusLabel,
  gradeBadgeText,
  hashSummaryLabel,
  isSafeLink,
  lowestEvidenceGrade,
  reportHashRows,
  resolveReportDetailState,
  templateLabel,
  type EvidenceGrade,
  type GateView,
  type ReportHashRow,
  type StatusTone,
} from "@/lib/reports-view";

type Props = { params: Promise<{ artifactId: string }> };

/*
 * 段名是 artifactId。这是 B5 任务给的路径。
 * 当前没有按产物 ID 读取的端点，所以页面把该值当作报告 ID，
 * 调用 `GET /api/reports/{report_id}`。报告列表也链接到报告 ID。
 */

/** 覆盖单元的状态标签。 */
const COVERAGE_STATUS_LABELS: Record<string, string> = {
  success: "有结果",
  empty: "空结果",
  failed: "失败",
};

/** 语义色到徽章边框与文字色。 */
function toneBadgeClass(tone: StatusTone): string {
  switch (tone) {
    case "success":
      return "border-[var(--state-success)] text-[var(--state-success)]";
    case "warning":
      return "border-[var(--state-warning)] text-[var(--state-warning)]";
    case "danger":
      return "border-[var(--state-danger)] text-[var(--state-danger)]";
    default:
      return "border-[var(--border-strong)] text-[var(--text-secondary)]";
  }
}

/**
 * 证据等级徽章。
 *
 * 形状是左侧加粗的方角徽章。claim 状态徽章是圆角描边。
 * 两者形状与字号不同，不靠颜色区分。
 */
function GradeBadge({ grade }: { grade: EvidenceGrade }) {
  return (
    <span
      className={`inline-flex items-center rounded-[var(--radius-1)] border border-l-2 bg-[var(--surface-muted)] px-2 py-0.5 font-mono text-[11px] font-semibold ${toneBadgeClass(
        EVIDENCE_GRADE_TONES[grade],
      )}`}
      title={EVIDENCE_GRADE_LABELS[grade]}
      aria-label={`证据等级 ${grade} ${EVIDENCE_GRADE_LABELS[grade]}`}
    >
      {gradeBadgeText(grade)}
    </span>
  );
}

/** claim 状态徽章。低于 L4 时 confirmed 显示为「状态越级」。 */
function ClaimBadge({
  status,
  grade,
}: {
  status: Claim["claim_status"];
  grade: EvidenceGrade;
}) {
  const display = claimStatusDisplay(status, grade);
  return (
    <span
      className={`inline-flex items-center rounded-full border bg-[var(--surface-primary)] px-2.5 py-0.5 text-xs font-medium ${toneBadgeClass(
        display.tone,
      )}`}
      title={status}
      aria-label={`claim 状态 ${status}`}
    >
      {display.label}
    </span>
  );
}

/** 首屏的一行状态。三行必须是独立节点。 */
function StatusRow({
  testId,
  label,
  children,
}: {
  testId: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <p
      data-testid={testId}
      className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm"
    >
      <span className="w-20 shrink-0 font-semibold text-[var(--text-tertiary)]">
        {label}
      </span>
      <span className="min-w-0 text-[var(--text-primary)]">{children}</span>
    </p>
  );
}

/** 三个哈希。默认折叠。缺失项按原因显示「未生成」或「接口未提供」。 */
function HashPanel({ rows }: { rows: ReportHashRow[] }) {
  return (
    <details className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3">
      <summary className="cursor-pointer text-sm font-semibold text-[var(--text-secondary)]">
        {hashSummaryLabel(rows)}
      </summary>
      <dl className="mt-3 grid gap-2">
        {rows.map(row => (
          <div
            key={row.key}
            data-testid={`hash-${row.key}`}
            className="grid gap-1 sm:grid-cols-[6rem_1fr] sm:items-baseline"
          >
            <dt className="text-xs font-semibold text-[var(--text-tertiary)]">
              {row.label}
            </dt>
            <dd
              className={`break-all font-mono text-xs ${
                row.value
                  ? "text-[var(--text-secondary)]"
                  : "text-[var(--text-tertiary)]"
              }`}
            >
              {row.display}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

/** 门禁列表。首屏只显示一条。详细列表展开后可见。 */
function GateList({ gates }: { gates: GateView[] }) {
  if (gates.length === 0) {
    return <p className="text-sm text-[var(--text-tertiary)]">合同没有门禁记录</p>;
  }
  return (
    <ul className="grid gap-1.5">
      {gates.map(gate => (
        <li
          key={gate.gate_id}
          className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-sm"
        >
          <span className="font-mono text-xs font-semibold text-[var(--text-secondary)]">
            {gate.gate_id}
          </span>
          <span
            className={
              gate.status === "pass"
                ? "text-[var(--state-success)]"
                : gate.status === "fail" || gate.status === "blocked"
                  ? "text-[var(--state-danger)]"
                  : "text-[var(--state-warning)]"
            }
          >
            {gateStatusLabel(gate.status)}
          </span>
          {gate.note ? (
            <span className="text-xs text-[var(--text-tertiary)]">{gate.note}</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

/** 一条证据。链接只允许安全协议。 */
function EvidenceRow({ evidence }: { evidence: Evidence }) {
  return (
    <li className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-[var(--text-secondary)]">
          {evidenceRoleLabel(evidence.role)}
        </span>
        <span className="font-mono text-xs text-[var(--text-tertiary)]">
          {evidence.source_tool_id}
        </span>
        <span className="text-xs text-[var(--text-tertiary)]">
          {evidence.market} · {formatTimestamp(evidence.captured_at)}
        </span>
        <GradeBadge grade={evidence.evidence_grade} />
      </div>
      {evidence.excerpt ? (
        <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-primary)]">
          {evidence.excerpt}
        </p>
      ) : null}
      {isSafeLink(evidence.url) ? (
        <a
          href={evidence.url ?? undefined}
          target="_blank"
          rel="noreferrer noopener"
          className="mt-1 inline-block text-xs font-medium text-[var(--action-primary)] hover:underline"
        >
          原文
        </a>
      ) : null}
    </li>
  );
}

/** 一条 claim 的阅读块。 */
function ClaimBlock({
  claim,
  evidences,
}: {
  claim: Claim;
  evidences: Evidence[];
}) {
  const forbidden = findForbiddenWords(claim.text, claim.evidence_grade);
  const claimEvidences = evidences.filter(
    item => item.claim_id === claim.claim_id,
  );

  return (
    <article className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
      <div className="flex flex-wrap items-center gap-2">
        <GradeBadge grade={claim.evidence_grade} />
        <ClaimBadge status={claim.claim_status} grade={claim.evidence_grade} />
        <code className="text-xs text-[var(--text-tertiary)]">
          {claim.claim_id}
        </code>
      </div>

      <h3 className="mt-3 text-lg font-semibold leading-snug text-[var(--text-primary)]">
        {claim.text}
      </h3>

      {forbidden.length > 0 ? (
        <p
          role="alert"
          className="mt-2 rounded-[var(--radius-2)] border border-[var(--state-danger)] px-3 py-2 text-xs text-[var(--state-danger)]"
        >
          文案违规：等级低于 L4，不得使用「{forbidden.join("」「")}」。
        </p>
      ) : null}

      <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[var(--text-tertiary)]">
        <div className="flex gap-1.5">
          <dt>市场</dt>
          <dd className="text-[var(--text-secondary)]">{claim.scope.market}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>时间窗</dt>
          <dd className="text-[var(--text-secondary)]">
            {formatPeriod(
              claim.scope.window.start,
              claim.scope.window.end,
            )}
          </dd>
        </div>
        <div className="flex gap-1.5">
          <dt>样本量</dt>
          <dd className="tabular-nums text-[var(--text-secondary)]">
            {claim.scope.sample_n}
          </dd>
        </div>
      </dl>

      <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">
        <span className="font-semibold text-[var(--text-primary)]">反证：</span>
        {claim.counterevidence_text}
      </p>

      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          证据 {claimEvidences.length} 条
        </summary>
        {claimEvidences.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">
            本 claim 没有可追溯证据。
          </p>
        ) : (
          <ul className="mt-2 grid gap-2">
            {claimEvidences.map(evidence => (
              <EvidenceRow key={evidence.evidence_id} evidence={evidence} />
            ))}
          </ul>
        )}
      </details>
    </article>
  );
}

/** 合同正文的阅读区。只用结构化字段。不注入 HTML。 */
function ContractBody({ contract }: { contract: ReportContract }) {
  return (
    <div className="grid gap-5">
      <section aria-labelledby="metrics-heading">
        <h2
          id="metrics-heading"
          className="text-base font-bold text-[var(--text-primary)]"
        >
          关键指标
        </h2>
        {contract.metrics.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">
            合同没有指标。
          </p>
        ) : (
          <div className="mt-2 overflow-x-auto rounded-[var(--radius-2)] border border-[var(--border-subtle)]">
            <table className="w-full min-w-[640px] border-collapse text-left text-sm">
              <caption className="sr-only">合同指标</caption>
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface-muted)] text-xs font-semibold text-[var(--text-tertiary)]">
                  <th scope="col" className="px-3 py-2">指标</th>
                  <th scope="col" className="px-3 py-2">数值</th>
                  <th scope="col" className="px-3 py-2">计数口径</th>
                  <th scope="col" className="px-3 py-2">帧</th>
                  <th scope="col" className="px-3 py-2">截至</th>
                </tr>
              </thead>
              <tbody>
                {contract.metrics.map(metric => (
                  <tr
                    key={metric.metric_id}
                    className="border-b border-[var(--border-subtle)] last:border-b-0"
                  >
                    <td className="px-3 py-2 font-medium text-[var(--text-primary)]">
                      {metric.label}
                      <span className="ml-2 font-mono text-xs text-[var(--text-tertiary)]">
                        {metric.metric_id}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {metric.numerator} / {metric.denominator}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {metric.count_type}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {metric.frame}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {metric.as_of}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="claims-heading">
        <h2
          id="claims-heading"
          className="text-base font-bold text-[var(--text-primary)]"
        >
          结论与证据
        </h2>
        {contract.claims.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">
            合同没有 claim。报告不得给出单一结论。
          </p>
        ) : (
          <div className="mt-2 grid gap-3">
            {contract.claims.map(claim => (
              <ClaimBlock
                key={claim.claim_id}
                claim={claim}
                evidences={contract.evidences}
              />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="coverage-heading">
        <h2
          id="coverage-heading"
          className="text-base font-bold text-[var(--text-primary)]"
        >
          覆盖
        </h2>
        {contract.coverage.cells.length === 0 ? (
          <p className="mt-2 text-sm text-[var(--text-tertiary)]">
            合同没有覆盖单元。
          </p>
        ) : (
          <div className="mt-2 overflow-x-auto rounded-[var(--radius-2)] border border-[var(--border-subtle)]">
            <table className="w-full min-w-[720px] border-collapse text-left text-sm">
              <caption className="sr-only">合同覆盖单元</caption>
              <thead>
                <tr className="border-b border-[var(--border-subtle)] bg-[var(--surface-muted)] text-xs font-semibold text-[var(--text-tertiary)]">
                  <th scope="col" className="px-3 py-2">数据源</th>
                  <th scope="col" className="px-3 py-2">市场</th>
                  <th scope="col" className="px-3 py-2">状态</th>
                  <th scope="col" className="px-3 py-2">记录数</th>
                  <th scope="col" className="px-3 py-2">帧成员</th>
                  <th scope="col" className="px-3 py-2">时间窗</th>
                </tr>
              </thead>
              <tbody>
                {contract.coverage.cells.map((cell, index) => (
                  <tr
                    key={`${cell.source_tool_id}-${cell.market}-${index}`}
                    className="border-b border-[var(--border-subtle)] last:border-b-0"
                  >
                    <td className="px-3 py-2 font-mono text-xs text-[var(--text-secondary)]">
                      {cell.source_tool_id}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {cell.market}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {COVERAGE_STATUS_LABELS[cell.status] ?? cell.status}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {cell.record_count}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-[var(--text-secondary)]">
                      {cell.frame_member_count}
                    </td>
                    <td className="px-3 py-2 text-[var(--text-secondary)]">
                      {formatPeriod(cell.window.start, cell.window.end)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-2" aria-label="限制与未知">
        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            本次不能推断什么
          </h2>
          {contract.limits.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--text-tertiary)]">
              合同没有限制条目。
            </p>
          ) : (
            <ul className="mt-2 grid list-disc gap-1 pl-5 text-sm text-[var(--text-secondary)]">
              {contract.limits.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            本次缺什么数据
          </h2>
          {contract.unknowns.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--text-tertiary)]">
              合同没有未知条目。
            </p>
          ) : (
            <ul className="mt-2 grid list-disc gap-1 pl-5 text-sm text-[var(--text-secondary)]">
              {contract.unknowns.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

export default function ReportReaderPage({ params }: Props) {
  const { artifactId } = use(params);

  const reportQuery = useQuery({
    queryKey: ["report", artifactId],
    queryFn: () => fetchReportById(artifactId),
  });

  const contractQuery = useQuery({
    queryKey: ["report-contract", artifactId],
    queryFn: () => fetchReportContract(artifactId),
    enabled: reportQuery.isSuccess,
    // 404 已由 fetchReportContract 分成端点缺失与资源未生成两种结果。
    // 其他错误仍抛给页面。
    retry: false,
  });

  const state = resolveReportDetailState({
    isLoading: reportQuery.isLoading,
    error: reportQuery.error,
    report: reportQuery.data,
  });

  const report = reportQuery.data ?? null;
  const contractResult = contractQuery.data;
  const contractBranch = contractRenderBranch(contractResult);
  const contract = contractResult?.kind === "ok" ? contractResult.contract : null;
  // 缺口结果只在端点缺失或资源未生成时出现。加载中与失败时不猜。
  const contractGap = isContractGapResult(contractResult)
    ? contractResult
    : null;
  const contractPending = contractQuery.isFetching;
  const contractFailed = contractQuery.isError;

  const hashes = reportHashRows({
    contract,
    // 端点缺失时，合同哈希与渲染哈希也来自缺失的接口。
    contractEndpointAvailable: contractBranch !== "endpoint_missing",
    // 后端没有报告产物端点。数据哈希不得显示「未生成」。
    dataEndpointAvailable: false,
  });

  const contractGapPanel = contractGap
    ? contractGapView({
        kind: contractGap.kind,
        endpoint: contractEndpointPath(artifactId),
      })
    : null;

  // 首屏状态行与模板徽章共用这段文案。不得把接口缺失写成数据未生成。
  const contractMissingText = contract
    ? null
    : contractPending
      ? "合同加载中"
      : contractGap
        ? contractAbsenceText(contractGap.kind)
        : contractFailed
          ? "合同加载失败"
          : "合同加载中";

  const lowest = contract ? lowestEvidenceGrade(contract.claims) : null;
  const gateText = contract ? gateLine(contract.gates) : null;
  const distribution = contract ? claimDistribution(contract.claims) : [];
  const distributionText = contract
    ? claimDistributionText(contract.claims)
    : null;

  return (
    <AppShell
      title={report?.title ?? "报告阅读"}
      description="结论、证据等级、门禁与三个哈希。"
      breadcrumbs={[
        { label: "报告中心", href: "/reports" },
        { label: report?.title ?? artifactId },
      ]}
    >
      {state === "loading" ? (
        <div className="grid gap-3" aria-label="报告加载中">
          <div className="h-10 w-2/3 animate-pulse rounded bg-[var(--surface-muted)]" />
          <div className="h-28 animate-pulse rounded-[var(--radius-3)] bg-[var(--surface-muted)]" />
          <div className="h-40 animate-pulse rounded-[var(--radius-3)] bg-[var(--surface-muted)]" />
        </div>
      ) : null}

      {state === "empty" ? (
        <div className="flex flex-col items-center rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-6 py-16 text-center">
          <FileText size={28} className="text-[var(--text-tertiary)]" aria-hidden="true" />
          <p className="mt-3 text-sm font-semibold text-[var(--text-primary)]">
            报告不存在
          </p>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">
            链接无效，或这份报告不在当前工作区。
          </p>
          <Link
            href="/reports"
            className="mt-4 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
          >
            返回报告中心
          </Link>
        </div>
      ) : null}

      {state === "error" ? (
        <div className="flex flex-col items-center rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-6 py-16 text-center">
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            报告加载失败
          </p>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">
            {reportQuery.error instanceof Error
              ? reportQuery.error.message
              : "请检查 API 连接后重试。"}
          </p>
          <button
            type="button"
            onClick={() => void reportQuery.refetch()}
            className="mt-4 flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)]"
          >
            <RefreshCw size={14} aria-hidden="true" />
            重试
          </button>
        </div>
      ) : null}

      {state === "ready" && report ? (
        <div className="mx-auto grid w-full max-w-[900px] gap-5">
          <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
            <Link
              href="/reports"
              className="flex items-center gap-1.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            >
              <ArrowLeft size={15} aria-hidden="true" />
              报告中心
            </Link>
            <button
              type="button"
              onClick={() => window.print()}
              className="flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            >
              <Printer size={14} aria-hidden="true" />
              打印
            </button>
          </div>

          {/* 首屏决策区。三行状态必须分开显示，不得合并成单一评分。 */}
          <header className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center rounded-full bg-[var(--accent-1-soft)] px-2.5 py-0.5 text-xs font-semibold text-[var(--action-primary)]">
                {contract ? templateLabel(contract.template_id) : contractMissingText}
              </span>
              <span className="text-xs text-[var(--text-tertiary)]">
                {report.status}
              </span>
            </div>

            <h1 className="mt-3 text-3xl font-bold leading-tight text-[var(--text-primary)]">
              {report.title}
            </h1>

            {contract ? (
              <>
                <p className="mt-3 text-base leading-relaxed text-[var(--text-secondary)]">
                  {contract.decision.decision_question}
                </p>
                <p className="mt-2 text-xl font-semibold leading-snug text-[var(--text-primary)]">
                  {contract.decision.answer}
                </p>
              </>
            ) : contractPending ? (
              <p className="mt-3 text-sm text-[var(--text-tertiary)]">
                正在读取报告合同…
              </p>
            ) : contractGapPanel ? (
              /*
                缺口分两种。端点缺失用 alert，并列出缺失的路径。
                用户必须能看出这不是自己的数据问题。
              */
              <div
                role={contractGapPanel.role}
                className={
                  contractGapPanel.role === "alert"
                    ? "mt-3 rounded-[var(--radius-2)] border border-[var(--state-danger)] px-3 py-2 text-xs text-[var(--state-danger)]"
                    : "mt-3 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2 text-sm text-[var(--text-secondary)]"
                }
              >
                <p className="font-semibold">{contractGapPanel.title}</p>
                <p className="mt-1 leading-relaxed">{contractGapPanel.hint}</p>
                {contractGapPanel.retryable ? (
                  <button
                    type="button"
                    onClick={() => void contractQuery.refetch()}
                    className="mt-2 flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                  >
                    <RefreshCw size={12} aria-hidden="true" />
                    重试
                  </button>
                ) : null}
              </div>
            ) : null}

            {contractFailed ? (
              <p
                role="alert"
                className="mt-3 rounded-[var(--radius-2)] border border-[var(--state-danger)] px-3 py-2 text-xs text-[var(--state-danger)]"
              >
                合同加载失败。{contractQuery.error instanceof Error
                  ? contractQuery.error.message
                  : ""}
              </p>
            ) : null}

            <div className="mt-5 grid gap-2 border-t border-[var(--border-subtle)] pt-4">
              <StatusRow testId="grade-line" label="证据等级">
                {contract ? (
                  lowest ? (
                    <>
                      <span className="font-semibold">最低 </span>
                      <GradeBadge grade={lowest} />
                    </>
                  ) : (
                    "无 claim"
                  )
                ) : (
                  <span className="text-[var(--text-tertiary)]">
                    {contractMissingText}
                  </span>
                )}
              </StatusRow>

              <StatusRow testId="gate-line" label="门禁">
                {contract ? (
                  gateText ?? (
                    <span className="text-[var(--text-tertiary)]">
                      合同没有门禁记录
                    </span>
                  )
                ) : (
                  <span className="text-[var(--text-tertiary)]">
                    {contractMissingText}
                  </span>
                )}
              </StatusRow>

              <StatusRow testId="claim-line" label="claim 分布">
                {contract ? (
                  distributionText
                ) : (
                  <span className="text-[var(--text-tertiary)]">
                    {contractMissingText}
                  </span>
                )}
              </StatusRow>
            </div>

            {contract ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {CLAIM_STATUSES.map(status => {
                  const row = distribution.find(item => item.status === status);
                  return (
                    <span
                      key={status}
                      className="rounded-full border border-[var(--border-subtle)] px-2 py-0.5 text-xs text-[var(--text-secondary)]"
                    >
                      {row?.label ?? status} {row?.count ?? 0}
                    </span>
                  );
                })}
              </div>
            ) : null}

            <div className="mt-4">
              <HashPanel rows={hashes} />
            </div>

            {contract && contract.gates.length > 0 ? (
              <details className="mt-3">
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
                  全部门禁（{contract.gates.length}）
                </summary>
                <div className="mt-2">
                  <GateList gates={contract.gates} />
                </div>
              </details>
            ) : null}
          </header>

          {contract ? (
            <ContractBody contract={contract} />
          ) : (
            <section aria-labelledby="legacy-body-heading">
              <h2
                id="legacy-body-heading"
                className="text-base font-bold text-[var(--text-primary)]"
              >
                旧版正文
              </h2>
              <p className="mt-1 text-xs text-[var(--text-tertiary)]">
                合同生成后，正文由服务端渲染器输出。这里只显示纯文本。
              </p>
              {/*
                安全：报告 HTML 必须来自服务端渲染器。
                `services/report_renderers.py` 用 `html.escape` 转义合同文本。
                链接只允许 http、https 或相对地址。信任来自服务端的转义。
                当前没有报告 HTML 产出端点，所以本页不注入 HTML。
              */}
              <div className="mt-2 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
                <pre className="whitespace-pre-wrap break-words font-sans text-[15px] leading-[1.66] text-[var(--text-primary)]">
                  {report.content}
                </pre>
              </div>
            </section>
          )}

          <p className="text-xs text-[var(--text-tertiary)]">
            报告周期：{formatPeriod(report.period_start, report.period_end)}
          </p>
        </div>
      ) : null}
    </AppShell>
  );
}
