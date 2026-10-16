"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PlatformLogo } from "@/components/platforms/platform-logo";
import { fetchCollectorCatalog } from "@/lib/api/collectors";
import type { CollectorEndpoint } from "@/lib/api/collectors";

/** 目录墙格数。取 catalog 前 24 条。 */
const WALL_SIZE = 24;

/**
 * 目录墙。
 *
 * 数据来自 GET /api/collectors/catalog 的前 24 行。
 * 每格是首字母方块、名称与一行说明。
 * 后端不可达时显示错误说明，CTA 格保留。
 * 末格链到 /tools。
 */
export function ToolWall() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["collector-catalog"],
    queryFn: fetchCollectorCatalog,
  });

  const allEndpoints: CollectorEndpoint[] = data
    ? data.collectors.flatMap(group => group.endpoints)
    : [];
  const wallEntries = allEndpoints.slice(0, WALL_SIZE);
  const totalCount = allEndpoints.length;

  return (
    <div>
      {isLoading && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5" aria-hidden="true">
          {Array.from({ length: 10 }, (_, i) => (
            <li
              key={i}
              className="h-32 animate-pulse rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] motion-reduce:animate-none"
            />
          ))}
        </ul>
      )}

      {!isLoading && error && (
        <p className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--state-danger)]">
          目录加载失败。打开「工具」页重试。
        </p>
      )}

      {!isLoading && !error && wallEntries.length === 0 && (
        <p className="mb-4 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-3 text-sm text-[var(--text-tertiary)]">
          目录暂无条目。打开「工具」页查看最新状态。
        </p>
      )}

      {!isLoading && !error && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {wallEntries.map(endpoint => (
            <li
              key={endpoint.endpoint_type}
              className="flex flex-col gap-3 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4"
            >
              <PlatformLogo platform={endpoint.platform} size={36} />
              <span className="line-clamp-2 min-h-10 text-sm font-medium leading-5 text-[var(--text-primary)]">
                {endpoint.label}
              </span>
              <span className="line-clamp-1 text-xs text-[var(--text-tertiary)]">
                {endpoint.description}
              </span>
            </li>
          ))}

          <li>
            <Link
              href="/tools"
              className="flex h-full min-h-32 flex-col justify-between rounded-[var(--radius-3)] border border-[var(--action-primary)] bg-[var(--accent-1-soft)] p-4 transition-colors hover:bg-[var(--surface-muted)]"
            >
              <ArrowRight size={18} className="text-[var(--action-primary)]" />
              <span className="text-sm font-medium leading-5 text-[var(--action-primary)]">
                {totalCount > 0 ? `查看全部 ${totalCount} 个能力视图` : "查看全部能力视图"}
              </span>
            </Link>
          </li>
        </ul>
      )}
    </div>
  );
}
