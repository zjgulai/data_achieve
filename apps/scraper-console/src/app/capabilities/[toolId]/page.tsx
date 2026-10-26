"use client";

import { use, type ReactNode } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError } from "@/lib/api/client";
import { fetchTool } from "@/lib/api/tools";
import type { PublicTool, ToolRiskClass } from "@/lib/api/tools";
import {
  RISK_CLASS_HINTS,
  RISK_CLASS_LABELS,
  RISK_CLASS_TONES,
  costHintOf,
  executabilityOf,
  type Tone,
} from "@/lib/capabilities";
import { resolveToolDetailState } from "@/lib/routes";

type Props = Readonly<{
  // 键名必须与目录名 [toolId] 一致。Next.js 按目录名传参。
  params: Promise<{ toolId: string }>;
}>;

/** 语义色的徽标样式。 */
const TONE_CLASSES: Record<Tone, string> = {
  success:
    "border-[var(--state-success)] bg-[var(--success-soft)] text-[var(--state-success)]",
  info:
    "border-[var(--state-info)] bg-[var(--accent-2-soft)] text-[var(--state-info)]",
  warning:
    "border-[var(--state-warning)] bg-[var(--warning-soft)] text-[var(--state-warning)]",
  muted:
    "border-[var(--border-strong)] bg-[var(--surface-muted)] text-[var(--text-tertiary)]",
  danger:
    "border-[var(--state-danger)] bg-[var(--danger-soft)] text-[var(--state-danger)]",
};

/** 一个语义徽标。 */
function Badge({
  tone,
  title,
  children,
}: {
  readonly tone: Tone;
  readonly title?: string;
  readonly children: ReactNode;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-[var(--radius-pill)] border px-2 py-0.5 text-[11px] font-semibold ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}

/** 风险类别徽标。 */
function RiskBadge({ risk }: { readonly risk: ToolRiskClass }) {
  return (
    <Badge tone={RISK_CLASS_TONES[risk]} title={RISK_CLASS_HINTS[risk]}>
      {RISK_CLASS_LABELS[risk]}
    </Badge>
  );
}

/** 把 ISO 时间转为本地时间。非法值原样返回。 */
function formatTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

/** 详情里的一个事实。 */
function Fact({
  label,
  value,
}: {
  readonly label: string;
  readonly value: string;
}) {
  return (
    <div>
      <dt className="text-[var(--text-tertiary)]">{label}</dt>
      <dd className="mt-0.5 break-all text-[var(--text-secondary)]">{value}</dd>
    </div>
  );
}

/** 完整工具详情。字段与 `PublicTool` 一一对应。 */
function ToolDetailBody({ tool }: { readonly tool: PublicTool }) {
  const execution = executabilityOf(tool);
  const cost = costHintOf(tool);
  const missing = tool.availability.missing_configuration;

  return (
    <div className="grid gap-5">
      <p className="text-sm leading-6 text-[var(--text-secondary)]">
        {tool.description}
      </p>

      <div className="flex flex-wrap gap-2">
        <RiskBadge risk={tool.risk_class} />
        <Badge tone={execution.tone} title={execution.detail}>
          {execution.label}
        </Badge>
        {tool.is_alias_view ? <Badge tone="muted">别名视图</Badge> : null}
      </div>

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          基本信息
        </h2>
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <Fact label="平台" value={tool.platform} />
          <Fact label="提供方" value={tool.provider} />
          <Fact label="提供方分组" value={tool.provider_group} />
          <Fact label="内容类型" value={tool.content_type} />
          <Fact label="输出类型" value={tool.output_kind} />
          <Fact label="运行模式" value={tool.run_mode} />
          <Fact label="执行类型" value={tool.execution_kind} />
          <Fact label="可取消" value={tool.cancellable ? "是" : "否"} />
        </dl>
      </section>

      <section className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] p-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          可执行性
        </h2>
        <p className="mt-1.5 text-sm font-semibold text-[var(--text-primary)]">
          {execution.label}
        </p>
        <p className="mt-0.5 text-xs leading-5 text-[var(--text-tertiary)]">
          {execution.detail}
        </p>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
          <Fact label="当前可执行" value={tool.executable_now ? "是" : "否"} />
          <Fact label="目录标记可执行" value={tool.executable ? "是" : "否"} />
          <Fact label="永久阻断" value={tool.permanently_blocked ? "是" : "否"} />
          <Fact label="可用性" value={tool.availability.availability} />
          <Fact label="目录状态" value={tool.availability.catalog_status} />
          <Fact
            label="最近实测"
            value={tool.availability.last_test_status ?? "无记录"}
          />
          <Fact
            label="最近实测时间"
            value={formatTime(tool.availability.last_test_at)}
          />
          <Fact
            label="最近记录数"
            value={
              tool.availability.last_records_count === null
                ? "—"
                : String(tool.availability.last_records_count)
            }
          />
        </dl>
        {missing.length > 0 ? (
          <p className="mt-2 text-xs text-[var(--state-warning)]">
            缺少配置：{missing.join("、")}
          </p>
        ) : null}
      </section>

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          成本提示
        </h2>
        <p className="mt-1.5 text-sm text-[var(--text-primary)]">{cost.text}</p>
        <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
          {cost.sourceLabel}。{cost.note}
        </p>
      </section>

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          参数（{tool.parameters.length}）
        </h2>
        {tool.parameters.length === 0 ? (
          <p className="mt-1.5 text-xs text-[var(--text-tertiary)]">
            该工具未登记参数。
          </p>
        ) : (
          <table className="mt-2 w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--border-subtle)] text-[var(--text-tertiary)]">
                <th className="py-1.5 pr-2 font-semibold">名称</th>
                <th className="py-1.5 pr-2 font-semibold">类型</th>
                <th className="py-1.5 font-semibold">说明</th>
              </tr>
            </thead>
            <tbody>
              {tool.parameters.map(parameter => (
                <tr
                  key={parameter.name}
                  className="border-b border-[var(--border-subtle)] last:border-0"
                >
                  <td className="py-1.5 pr-2 font-mono text-[var(--text-secondary)]">
                    {parameter.name}
                    {parameter.required ? (
                      <span className="ml-0.5 text-[var(--state-danger)]">*</span>
                    ) : null}
                  </td>
                  <td className="py-1.5 pr-2 text-[var(--text-secondary)]">
                    {parameter.typed
                      ? (parameter.value_type ?? "未登记类型")
                      : "未登记类型"}
                  </td>
                  <td className="py-1.5 text-[var(--text-tertiary)]">
                    {parameter.description ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
          调用方式
        </h2>
        <p className="mt-1.5 break-all text-xs text-[var(--text-secondary)]">
          REST：<code className="font-mono">GET /api/tools/{tool.tool_id}</code>
        </p>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          MCP：先调用 <code className="font-mono">list_capabilities</code>，再用工具标识调用。
        </p>
        {tool.is_alias_view ? (
          <p className="mt-1 break-all text-xs text-[var(--text-tertiary)]">
            主条目：<span className="font-mono">{tool.canonical_tool_id}</span>
          </p>
        ) : null}
      </section>
    </div>
  );
}

/** 居中提示块。加载、404 与错误共用。 */
function StateBlock({ children }: { readonly children: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-6 py-16 text-center">
      {children}
    </div>
  );
}

/** 返回列表的链接。 */
function BackLink() {
  return (
    <Link
      href="/capabilities"
      className="inline-flex items-center gap-1.5 rounded-[var(--radius-2)] text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
    >
      <ArrowLeft size={14} aria-hidden="true" />
      返回能力目录
    </Link>
  );
}

/**
 * 能力详情深链。
 *
 * 段名是 toolId。路径参数由 Next.js 传入，客户端只调用
 * `GET /api/tools/{tool_id}`。不做服务端预取。
 */
export default function CapabilityDetailPage({ params }: Props) {
  const { toolId } = use(params);

  const detail = useQuery({
    queryKey: ["tool", toolId],
    queryFn: () => fetchTool(toolId),
    // 404 不重试。工具不存在时重试没有意义。
    retry: (failureCount, error) =>
      error instanceof ApiError && error.status === 404
        ? false
        : failureCount < 2,
  });

  const state = resolveToolDetailState({
    isLoading: detail.isLoading,
    error: detail.error,
    hasTool: Boolean(detail.data),
  });

  return (
    <AppShell
      title={detail.data?.label ?? "能力详情"}
      description={detail.data?.tool_id ?? toolId}
      breadcrumbs={[
        { label: "能力目录", href: "/capabilities" },
        { label: detail.data?.label ?? toolId },
      ]}
    >
      <div>
        <BackLink />
      </div>

      {state === "loading" ? (
        <StateBlock>
          <Loader2
            size={22}
            className="animate-spin text-[var(--text-tertiary)] motion-reduce:animate-none"
            aria-hidden="true"
          />
          <p className="text-sm text-[var(--text-tertiary)]">正在加载工具详情…</p>
        </StateBlock>
      ) : state === "not-found" ? (
        <StateBlock>
          <h2 className="text-base font-bold text-[var(--text-primary)]">工具不存在</h2>
          <p className="max-w-lg text-sm leading-6 text-[var(--text-secondary)]">
            未找到标识为{" "}
            <code className="font-mono text-xs text-[var(--text-primary)]">{toolId}</code>{" "}
            的工具。它可能已下线或改名。
          </p>
          <div className="mt-2">
            <BackLink />
          </div>
        </StateBlock>
      ) : state === "error" ? (
        <StateBlock>
          <h2 className="text-base font-bold text-[var(--text-primary)]">详情加载失败</h2>
          <p className="max-w-lg text-sm leading-6 text-[var(--state-danger)]">
            {detail.error instanceof Error ? detail.error.message : "未知错误"}
          </p>
          <button
            type="button"
            onClick={() => detail.refetch()}
            className="mt-2 inline-flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
          >
            <RefreshCw size={12} aria-hidden="true" />
            重试
          </button>
        </StateBlock>
      ) : detail.data ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-6">
          <ToolDetailBody tool={detail.data} />
        </div>
      ) : null}
    </AppShell>
  );
}
