"use client";

import {
  ArrowUpRight,
  DatabaseZap,
  Filter,
  Search,
  ShieldCheck,
  Store,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import {
  apiMarketEndpoints,
  buildApiMarketStats,
  filterApiMarketEndpoints,
} from "@/lib/api-market-catalog";
import type { Route } from "next";
import type {
  ApiMarketCategory,
  ApiMarketExecutionMode,
  ApiMarketFilterState,
  ApiMarketPlatform,
  ApiMarketPriority,
  ApiMarketStability,
} from "@/types/api-market";
import { WorkbenchFact, WorkbenchPanel, WorkbenchTag } from "@/components/common/workbench-ui";

const platforms: Array<ApiMarketPlatform | "all"> = [
  "all",
  "youtube",
  "reddit",
  "x",
  "instagram",
  "threads",
  "tiktok",
  "linkedin",
];

const categories: Array<ApiMarketCategory | "all"> = [
  "all",
  "content_search",
  "video_detail",
  "comment_threads",
  "post_search",
  "post_lookup",
  "creator_profile",
  "media_feed",
  "mentions",
  "insights",
  "research",
  "organization_updates",
];

const priorities: Array<ApiMarketPriority | "all"> = ["all", "p0", "p1", "p2", "p3"];
const stabilities: Array<ApiMarketStability | "all"> = ["all", "high", "medium", "low"];
const executionModes: Array<ApiMarketExecutionMode | "all"> = [
  "all",
  "fixture_ready",
  "adapter_planned",
  "live_gated",
];

export function ApiMarketWorkspace() {
  const [filters, setFilters] = useState<ApiMarketFilterState>({
    category: "all",
    executionMode: "all",
    platform: "all",
    priority: "all",
    query: "",
    stability: "all",
  });

  const endpoints = useMemo(() => filterApiMarketEndpoints(filters), [filters]);
  const stats = useMemo(() => buildApiMarketStats(apiMarketEndpoints), []);

  function patchFilters(next: Partial<ApiMarketFilterState>) {
    setFilters((current) => ({ ...current, ...next }));
  }

  return (
    <div className="grid min-w-0 gap-5">
      <WorkbenchPanel
        action={<WorkbenchTag tone="neutral">provider_call=false</WorkbenchTag>}
        icon={Store}
        label="API Market"
        subtitle="Marketplace-style endpoint catalog with no provider call by default"
        title="海外社媒 API 私有化市场"
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <WorkbenchFact label="platforms" value={String(stats.platformCount)} />
          <WorkbenchFact label="endpoints" value={String(stats.endpointCount)} />
          <WorkbenchFact label="p0_official" value={String(stats.p0Count)} />
          <WorkbenchFact label="fixture_ready" value={String(stats.fixtureReadyCount)} />
          <WorkbenchFact label="live_gated" value={String(stats.liveGatedCount)} />
        </div>
      </WorkbenchPanel>

      <section className="grid min-w-0 gap-3 rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
        <label className="grid min-w-0 gap-2 text-sm font-semibold text-[#3B2924]">
          <span className="inline-flex items-center gap-2">
            <Search size={15} aria-hidden="true" />
            搜索 API、平台、endpoint 或 policy flag
          </span>
          <input
            className="h-11 w-full min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
            onChange={(event) => patchFilters({ query: event.target.value })}
            placeholder="videos.list / Reddit / comments / no_ai_training"
            value={filters.query}
          />
        </label>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <SelectFilter
            label="平台"
            onChange={(value) =>
              patchFilters({ platform: value as ApiMarketFilterState["platform"] })
            }
            options={platforms}
            value={filters.platform}
          />
          <SelectFilter
            label="分类"
            onChange={(value) =>
              patchFilters({ category: value as ApiMarketFilterState["category"] })
            }
            options={categories}
            value={filters.category}
          />
          <SelectFilter
            label="优先级"
            onChange={(value) =>
              patchFilters({ priority: value as ApiMarketFilterState["priority"] })
            }
            options={priorities}
            value={filters.priority}
          />
          <SelectFilter
            label="稳定性"
            onChange={(value) =>
              patchFilters({ stability: value as ApiMarketFilterState["stability"] })
            }
            options={stabilities}
            value={filters.stability}
          />
          <SelectFilter
            label="执行状态"
            onChange={(value) =>
              patchFilters({ executionMode: value as ApiMarketFilterState["executionMode"] })
            }
            options={executionModes}
            value={filters.executionMode}
          />
        </div>
      </section>

      <section className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {endpoints.map((endpoint) => (
          <article
            className="grid min-w-0 gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4"
            key={endpoint.id}
          >
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase text-[#B47767]">
                  {endpoint.platformLabel}
                </p>
                <h2 className="mt-1 break-words text-base font-semibold text-[#2E201C]">
                  {endpoint.title}
                </h2>
              </div>
              <WorkbenchTag tone={endpoint.priority === "p0" ? "green" : "amber"}>
                {endpoint.priority}
              </WorkbenchTag>
            </div>

            <p className="break-all rounded-xl bg-white px-3 py-2 text-sm font-semibold text-[#3B2924]">
              {endpoint.method} / {endpoint.endpoint}
            </p>
            <p className="text-sm leading-6 text-[#7A625A]">{endpoint.summary}</p>

            <div className="flex flex-wrap gap-2">
              <WorkbenchTag tone="muted">{endpoint.category}</WorkbenchTag>
              <WorkbenchTag tone={stabilityTone(endpoint.stability)}>
                {endpoint.stability}
              </WorkbenchTag>
              <WorkbenchTag tone="neutral">{endpoint.executionMode}</WorkbenchTag>
            </div>

            <div className="grid gap-2 text-xs text-[#7A625A]">
              <span className="inline-flex min-w-0 items-center gap-2 break-all">
                <DatabaseZap size={14} className="shrink-0" aria-hidden="true" />
                {endpoint.sdkPackage}
              </span>
              <span className="inline-flex min-w-0 items-center gap-2 break-words">
                <ShieldCheck size={14} className="shrink-0" aria-hidden="true" />
                {endpoint.policyFlags.slice(0, 2).join(" / ")}
              </span>
              <span className="inline-flex min-w-0 items-center gap-2 break-words">
                <Zap size={14} className="shrink-0" aria-hidden="true" />
                {endpoint.costHint}
              </span>
            </div>

            <div className="flex flex-wrap gap-2 pt-1">
              <Link
                className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white"
                href={typedRoute(`/api-market/${endpoint.id}`)}
              >
                查看详情
                <ArrowUpRight size={15} aria-hidden="true" />
              </Link>
              <Link
                className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7A625A]"
                href={typedRoute(
                  `/automation?platform=${endpoint.platform}&endpoint=${encodeURIComponent(endpoint.endpoint)}`,
                )}
              >
                生成预案
              </Link>
            </div>
          </article>
        ))}
      </section>

      {endpoints.length === 0 ? (
        <section className="rounded-2xl border border-[#E8D4CB] bg-white p-6 text-center text-sm font-semibold text-[#7A625A]">
          没有找到匹配的 API endpoint。
        </section>
      ) : null}
    </div>
  );
}

function SelectFilter({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: readonly string[];
  value: string;
}) {
  return (
    <label className="grid min-w-0 gap-2 text-xs font-semibold uppercase text-[#B47767]">
      <span className="inline-flex items-center gap-2">
        <Filter size={13} aria-hidden="true" />
        {label}
      </span>
      <select
        className="h-10 w-full min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm normal-case text-[#3B2924] outline-none"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === "all" ? "全部" : option}
          </option>
        ))}
      </select>
    </label>
  );
}

function typedRoute(href: string): Route {
  return href as Route;
}

function stabilityTone(stability: ApiMarketStability): "amber" | "green" | "rose" {
  if (stability === "high") {
    return "green";
  }
  if (stability === "medium") {
    return "amber";
  }
  return "rose";
}
