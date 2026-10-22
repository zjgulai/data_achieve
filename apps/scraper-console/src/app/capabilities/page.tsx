"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { fetchTools } from "@/lib/api/tools";
import type { PublicTool, ToolRiskClass } from "@/lib/api/tools";
import { fetchToolCatalogSummary } from "@/lib/api/tool-catalog";
import {
  RISK_CLASS_HINTS,
  RISK_CLASS_LABELS,
  RISK_CLASS_ORDER,
  RISK_CLASS_TONES,
  costHintOf,
  executabilityOf,
  hasActiveFilters,
  listState,
  paginate,
  parseExecutableFilter,
  parsePage,
  parseRiskClass,
  type Tone,
} from "@/lib/capabilities";
import {
  SEARCH_DEBOUNCE_MS,
  hrefWithParams,
  mergeParams,
  type ParamUpdates,
} from "@/lib/url-state";
import { openToolDetail } from "@/lib/routes";

/** 每页条数。工具约 283 条，一次全渲染会很慢。 */
const PAGE_SIZE = 20;

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

/** 页头的目录摘要。摘要失败不阻断列表。 */
function CatalogSummary() {
  const summary = useQuery({
    queryKey: ["tool-catalog-summary"],
    queryFn: fetchToolCatalogSummary,
  });

  if (summary.isLoading) {
    return (
      <div
        aria-hidden="true"
        className="h-10 animate-pulse rounded-[var(--radius-2)] bg-[var(--surface-muted)] motion-reduce:animate-none"
      />
    );
  }

  if (summary.error || !summary.data) {
    return (
      <p className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-2.5 text-xs text-[var(--text-tertiary)]">
        目录摘要暂不可用。列表仍可读取。
      </p>
    );
  }

  const data = summary.data;
  return (
    <dl className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-2.5 text-xs">
      <div>
        <dt className="inline text-[var(--text-tertiary)]">目录版本 </dt>
        <dd className="inline font-mono text-[var(--text-secondary)]">
          {data.schema_version}
        </dd>
      </div>
      <div>
        <dt className="inline text-[var(--text-tertiary)]">契约 </dt>
        <dd className="inline font-mono text-[var(--text-secondary)]">
          {data.contract_version}
        </dd>
      </div>
      <div title={data.catalog_digest}>
        <dt className="inline text-[var(--text-tertiary)]">摘要 </dt>
        <dd className="inline font-mono text-[var(--text-secondary)]">
          {data.catalog_digest.slice(0, 12)}…
        </dd>
      </div>
      <div>
        <dt className="inline text-[var(--text-tertiary)]">视图 </dt>
        <dd className="inline tabular-nums text-[var(--text-secondary)]">
          {data.tool_count}
        </dd>
      </div>
      <div>
        <dt className="inline text-[var(--text-tertiary)]">唯一端点 </dt>
        <dd className="inline tabular-nums text-[var(--text-secondary)]">
          {data.canonical_tool_count}
        </dd>
      </div>
      <div>
        <dt className="inline text-[var(--text-tertiary)]">目录可执行 </dt>
        <dd className="inline tabular-nums text-[var(--text-secondary)]">
          {data.executable_count}
        </dd>
      </div>
    </dl>
  );
}

/** 一行工具。名称格内是按钮，键盘可打开详情。 */
function ToolRow({
  tool,
  onOpen,
}: {
  readonly tool: PublicTool;
  readonly onOpen: (toolId: string) => void;
}) {
  const execution = executabilityOf(tool);
  const cost = costHintOf(tool);

  return (
    <tr
      className="cursor-pointer border-b border-[var(--border-subtle)] transition-colors duration-[var(--duration-fast)] last:border-0 hover:bg-[var(--surface-muted)]"
      onClick={() => onOpen(tool.tool_id)}
    >
      <td className="h-14 px-4 py-2 align-middle">
        <button
          type="button"
          onClick={event => {
            event.stopPropagation();
            onOpen(tool.tool_id);
          }}
          className="block max-w-full text-left"
          aria-label={`进入 ${tool.label} 的详情页`}
        >
          <span className="block truncate text-sm font-semibold text-[var(--text-primary)]">
            {tool.label}
          </span>
          <span className="mt-0.5 block truncate font-mono text-[11px] text-[var(--text-tertiary)]">
            {tool.tool_id}
          </span>
        </button>
      </td>
      <td className="px-4 py-2 align-middle text-xs text-[var(--text-secondary)]">
        {tool.platform}
      </td>
      <td className="px-4 py-2 align-middle text-xs text-[var(--text-secondary)]">
        {tool.provider}
      </td>
      <td className="px-4 py-2 align-middle">
        <RiskBadge risk={tool.risk_class} />
      </td>
      <td className="px-4 py-2 align-middle">
        <Badge tone={execution.tone} title={execution.detail}>
          {execution.label}
        </Badge>
      </td>
      <td className="px-4 py-2 align-middle">
        <span
          className="block max-w-[220px] truncate text-xs text-[var(--text-secondary)]"
          title={cost.text}
        >
          {cost.text}
        </span>
        <span className="mt-0.5 block text-[11px] text-[var(--text-tertiary)]">
          {cost.sourceLabel}
        </span>
      </td>
    </tr>
  );
}

/** 加载态的占位行。行高与真实行一致。 */
function LoadingRows() {
  return (
    <div aria-label="正在加载能力目录" className="divide-y divide-[var(--border-subtle)]">
      {Array.from({ length: 12 }, (_, index) => (
        <div key={index} className="flex h-14 items-center gap-4 px-4">
          <div className="h-3 w-44 animate-pulse rounded bg-[var(--surface-muted)] motion-reduce:animate-none" />
          <div className="h-3 w-16 animate-pulse rounded bg-[var(--surface-muted)] motion-reduce:animate-none" />
          <div className="h-3 w-20 animate-pulse rounded bg-[var(--surface-muted)] motion-reduce:animate-none" />
          <div className="h-5 w-14 animate-pulse rounded-full bg-[var(--surface-muted)] motion-reduce:animate-none" />
          <div className="h-5 w-20 animate-pulse rounded-full bg-[var(--surface-muted)] motion-reduce:animate-none" />
        </div>
      ))}
    </div>
  );
}

/** 页面主体。筛选状态存在 URL。 */
function CapabilitiesPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const query = (searchParams.get("query") ?? "").trim();
  const riskClass = parseRiskClass(searchParams.get("risk_class"));
  const executableNow = parseExecutableFilter(
    searchParams.get("executable_now"),
  );
  const requestedPage = parsePage(searchParams.get("page"));

  // 搜索框草稿。它只在其基准值仍是当前 URL 值时生效。
  const [searchDraft, setSearchDraft] = useState<{
    base: string;
    value: string;
  } | null>(null);
  const searchValue =
    searchDraft && searchDraft.base === query ? searchDraft.value : query;

  const applyParams = useCallback(
    (updates: ParamUpdates) => {
      const next = mergeParams(
        new URLSearchParams(searchParams.toString()),
        updates,
      );
      router.replace(hrefWithParams(pathname, next), { scroll: false });
    },
    [pathname, router, searchParams],
  );

  // 防抖后把搜索词写入 URL。Enter 会立即提交。
  useEffect(() => {
    if (searchDraft === null) return;
    const value = searchDraft.value.trim();
    if (value === query) return;
    const timer = setTimeout(() => {
      applyParams({ query: value || null, page: null });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [applyParams, query, searchDraft]);

  const toolsQuery = useQuery({
    queryKey: ["tools", query, riskClass, executableNow],
    queryFn: () => fetchTools({ query, riskClass, executableNow }),
  });

  const tools = useMemo(() => toolsQuery.data?.tools ?? [], [toolsQuery.data]);
  const pageData = useMemo(
    () => paginate(tools, requestedPage, PAGE_SIZE),
    [requestedPage, tools],
  );
  const state = listState({
    isLoading: toolsQuery.isLoading,
    hasError: toolsQuery.error !== null,
    itemCount: tools.length,
  });
  const filtered = hasActiveFilters({ query, riskClass, executableNow });

  function clearAllFilters() {
    setSearchDraft(null);
    applyParams({
      query: null,
      risk_class: null,
      executable_now: null,
      page: null,
    });
  }

  function clearSearch() {
    setSearchDraft(null);
    applyParams({ query: null, page: null });
  }

  return (
    <AppShell
      title="能力目录"
      description="浏览采集与洞察工具，按关键词、风险类别和可执行性筛选"
      brief="每一行是一个工具视图。点击行可查看参数、成本与可执行性详情。"
    >
      <CatalogSummary />

      <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[240px] flex-1">
            <Search
              size={14}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]"
            />
            <input
              type="search"
              value={searchValue}
              onChange={event =>
                setSearchDraft({ base: query, value: event.target.value })
              }
              onKeyDown={event => {
                if (event.key === "Enter") {
                  const value = searchValue.trim();
                  setSearchDraft(null);
                  applyParams({ query: value || null, page: null });
                }
                if (event.key === "Escape") clearSearch();
              }}
              placeholder="搜索名称、标识、说明或平台"
              aria-label="搜索能力"
              className="h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] pl-9 pr-9 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none"
            />
            {searchValue ? (
              <button
                type="button"
                onClick={clearSearch}
                aria-label="清空搜索"
                className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-[var(--radius-1)] text-[var(--text-tertiary)] hover:bg-[var(--surface-muted)]"
              >
                <X size={13} aria-hidden="true" />
              </button>
            ) : null}
          </div>

          <label className="flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
            风险类别
            <select
              value={riskClass ?? "all"}
              onChange={event =>
                applyParams({
                  risk_class:
                    event.target.value === "all" ? null : event.target.value,
                  page: null,
                })
              }
              className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-2 text-xs text-[var(--text-primary)]"
            >
              <option value="all">全部</option>
              {RISK_CLASS_ORDER.map(value => (
                <option key={value} value={value}>
                  {RISK_CLASS_LABELS[value]}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
            可执行性
            <select
              value={executableNow === null ? "all" : String(executableNow)}
              onChange={event =>
                applyParams({
                  executable_now:
                    event.target.value === "all" ? null : event.target.value,
                  page: null,
                })
              }
              className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-2 text-xs text-[var(--text-primary)]"
            >
              <option value="all">全部</option>
              <option value="true">当前可执行</option>
              <option value="false">当前不可执行</option>
            </select>
          </label>

          {filtered ? (
            <button
              type="button"
              onClick={clearAllFilters}
              className="inline-flex h-9 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            >
              <X size={12} aria-hidden="true" />
              清除筛选
            </button>
          ) : null}
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--text-tertiary)]">
        <p>
          共 {tools.length} 条
          {filtered ? "（已筛选）" : ""}
        </p>
        {toolsQuery.isFetching && !toolsQuery.isLoading ? (
          <span className="inline-flex items-center gap-1.5">
            <Loader2
              size={12}
              className="animate-spin motion-reduce:animate-none"
              aria-hidden="true"
            />
            正在更新
          </span>
        ) : null}
      </div>

      <div className="overflow-hidden rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
        {state === "loading" ? (
          <LoadingRows />
        ) : state === "error" ? (
          <div className="p-10 text-center">
            <p className="text-sm text-[var(--state-danger)]">
              目录加载失败：
              {toolsQuery.error instanceof Error
                ? toolsQuery.error.message
                : "未知错误"}
            </p>
            <button
              type="button"
              onClick={() => toolsQuery.refetch()}
              className="mt-3 inline-flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            >
              <RefreshCw size={12} aria-hidden="true" />
              重试
            </button>
          </div>
        ) : state === "empty" ? (
          <div className="p-10 text-center">
            <p className="text-sm text-[var(--text-secondary)]">
              {filtered ? "没有匹配的能力视图。" : "目录暂无条目。"}
            </p>
            <p className="mt-1 text-xs text-[var(--text-tertiary)]">
              {filtered
                ? "清除筛选后可看到全部工具。"
                : "目录同步后可再次加载。"}
            </p>
            {filtered ? (
              <button
                type="button"
                onClick={clearAllFilters}
                className="mt-3 inline-flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              >
                <X size={12} aria-hidden="true" />
                清除全部筛选
              </button>
            ) : (
              <button
                type="button"
                onClick={() => toolsQuery.refetch()}
                className="mt-3 inline-flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              >
                <RefreshCw size={12} aria-hidden="true" />
                重新加载
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)]">
                    {[
                      "工具",
                      "平台",
                      "提供方",
                      "风险类别",
                      "可执行性",
                      "成本提示",
                    ].map(header => (
                      <th
                        key={header}
                        scope="col"
                        className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]"
                      >
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pageData.items.map(tool => (
                    <ToolRow
                      key={tool.tool_id}
                      tool={tool}
                      onOpen={toolId => openToolDetail(router, toolId)}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border-subtle)] px-4 py-3">
              <p className="text-xs text-[var(--text-tertiary)]">
                第 {pageData.start}–{pageData.end} 条，共 {pageData.total} 条
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={pageData.page <= 1}
                  onClick={() =>
                    applyParams({
                      page:
                        pageData.page <= 2 ? null : String(pageData.page - 1),
                    })
                  }
                  className="inline-flex items-center gap-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-40"
                >
                  <ChevronLeft size={12} aria-hidden="true" />
                  上一页
                </button>
                <span className="text-xs tabular-nums text-[var(--text-tertiary)]">
                  第 {pageData.page} / {pageData.totalPages} 页
                </span>
                <button
                  type="button"
                  disabled={pageData.page >= pageData.totalPages}
                  onClick={() =>
                    applyParams({ page: String(pageData.page + 1) })
                  }
                  className="inline-flex items-center gap-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] disabled:opacity-40"
                >
                  下一页
                  <ChevronRight size={12} aria-hidden="true" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

    </AppShell>
  );
}

export default function CapabilitiesPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="能力目录" description="加载能力目录">
          <div className="flex items-center justify-center py-24">
            <Loader2
              size={22}
              className="animate-spin text-[var(--text-tertiary)] motion-reduce:animate-none"
              aria-hidden="true"
            />
            <span className="ml-2 text-sm text-[var(--text-tertiary)]">
              正在加载能力目录…
            </span>
          </div>
        </AppShell>
      }
    >
      <CapabilitiesPageContent />
    </Suspense>
  );
}
