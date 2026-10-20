"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchCollectorDocs } from "@/lib/api/collector-docs";
import { fetchToolCatalogSummary } from "@/lib/api/tool-catalog";

/**
 * 统计条。
 *
 * 四个数全部来自接口，不写死：
 *   能力视图  GET /api/tool-catalog 的 tool_count
 *   唯一端点  GET /api/tool-catalog 的 canonical_tool_count
 *   已实测    GET /api/collectors/docs 的 tested_endpoints
 *   实测成功  GET /api/collectors/docs 的 success_endpoints
 *
 * 两接口都不可达时不显示数字，避免把 0 当成真实值。
 * 摘要码放在脚注，用来核对目录版本。
 */
export function StatBar() {
  const catalog = useQuery({
    queryKey: ["tool-catalog-summary"],
    queryFn: fetchToolCatalogSummary,
  });
  const docs = useQuery({
    queryKey: ["collector-docs"],
    queryFn: fetchCollectorDocs,
  });

  const failed = catalog.isError || docs.isError;
  const loading = catalog.isLoading || docs.isLoading;

  const stats = [
    {
      label: "能力视图",
      value: catalog.data ? String(catalog.data.tool_count) : null,
      note: "catalog 条目",
    },
    {
      label: "唯一端点",
      value: catalog.data ? String(catalog.data.canonical_tool_count) : null,
      note: "按 endpoint_type 去重",
    },
    {
      label: "已实测",
      value: docs.data ? String(docs.data.tested_endpoints) : null,
      note: "有生产运行记录",
    },
    {
      label: "实测成功",
      value: docs.data ? String(docs.data.success_endpoints) : null,
      note: "返回过 ≥1 条记录",
    },
  ];

  if (failed) {
    return (
      <p className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--state-danger)]">
        计数暂时读取不到。接口恢复后刷新本页。
      </p>
    );
  }

  return (
    <>
      <dl className="grid grid-cols-2 gap-8 lg:grid-cols-4">
        {stats.map(stat => (
          <div key={stat.label}>
            <dt className="text-sm text-[var(--text-secondary)]">{stat.label}</dt>
            <dd className="mt-1 text-[40px] font-semibold leading-[46px] tabular-nums">
              {loading ? (
                <span
                  aria-hidden="true"
                  className="inline-block h-[46px] w-20 animate-pulse rounded-[var(--radius-2)] bg-[var(--surface-muted)] motion-reduce:animate-none"
                />
              ) : (
                (stat.value ?? "—")
              )}
            </dd>
            <dd className="mt-1 text-xs text-[var(--text-tertiary)]">{stat.note}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-10 text-xs text-[var(--text-tertiary)]">
        来源：GET /api/tool-catalog 与 GET /api/collectors/docs，实时读取。
        {catalog.data ? ` 目录摘要 ${catalog.data.catalog_digest.slice(0, 12)}…` : ""}
      </p>
    </>
  );
}
