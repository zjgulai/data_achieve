"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Box, Cable, Search, ServerCog } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { fetchPlatformPackages, fetchProviderStatus } from "@/lib/api/platform-packages";
import type { EndpointAvailability, PlatformPackage } from "@/lib/api/platform-packages";
import {
  collectMethods,
  filterPlatformPackages,
} from "@/lib/skills/filter-platform-packages";

function PlatformMark({ name }: { readonly name: string }) {
  const letters = name.replace(/[^a-zA-Z0-9\u4e00-\u9fff]/g, "").slice(0, 2);
  return (
    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[var(--radius-3)] border border-[var(--border-strong)] bg-[var(--surface-muted)] text-xs font-bold text-[var(--text-primary)]">
      {letters || "DI"}
    </span>
  );
}

function PackageCard({ item, availability }: { readonly item: PlatformPackage; readonly availability: readonly EndpointAvailability[] }) {
  const ratio = item.endpoint_count
    ? Math.round((item.verified_count / item.endpoint_count) * 100)
    : 0;
  const degraded = availability.filter((entry) => entry.availability === "degraded").length;
  const gated = availability.filter((entry) => entry.availability === "config-gated").length;
  return (
    <Link
      href={`/skills/${encodeURIComponent(item.platform_id)}`}
      className="group flex min-h-64 flex-col rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5 transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--surface-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--action-primary)]"
    >
      <div className="flex items-start gap-3">
        <PlatformMark name={item.display_name} />
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-base font-bold text-[var(--text-primary)]">
            {item.display_name}
          </h2>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            {item.endpoint_count} 个能力视图 · {item.provider_groups.length} 个 Provider
          </p>
        </div>
        <span className="rounded-full border border-[var(--state-success)] bg-[var(--success-soft)] px-2 py-1 text-[10px] font-semibold text-[var(--state-success)]">
          {ratio}% verified
        </span>
      </div>
      <p className="mt-4 line-clamp-3 text-sm leading-6 text-[var(--text-secondary)]">
        {item.description}
      </p>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {item.methods.slice(0, 4).map((method) => (
          <span
            key={method}
            className="rounded-[var(--radius-1)] border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-2 py-1 font-mono text-[10px] text-[var(--text-tertiary)]"
          >
            {method}
          </span>
        ))}
      </div>
      {(degraded > 0 || gated > 0) && (
        <p className="mt-3 text-xs text-[var(--state-warning)]">
          {degraded > 0 ? `${degraded} 个 degraded` : ""}
          {degraded > 0 && gated > 0 ? " · " : ""}
          {gated > 0 ? `${gated} 个 config-gated` : ""}
        </p>
      )}
      <div className="mt-auto grid grid-cols-3 gap-2 border-t border-[var(--border-subtle)] pt-4 text-[11px] text-[var(--text-tertiary)]">
        <span className="flex items-center gap-1"><Box size={12} />Skill</span>
        <span className="flex items-center gap-1"><Cable size={12} />MCP</span>
        <span className="flex items-center gap-1"><BookOpen size={12} />Playbook</span>
      </div>
    </Link>
  );
}

export function SkillsDirectory() {
  const [query, setQuery] = useState("");
  const [method, setMethod] = useState("");
  const [status, setStatus] = useState<"all" | "verified" | "pending" | "disabled">("all");
  const [availability, setAvailability] = useState<"all" | EndpointAvailability["availability"]>("all");
  const { data, error, isLoading } = useQuery({
    queryKey: ["platform-packages"],
    queryFn: fetchPlatformPackages,
  });
  const statusQuery = useQuery({
    queryKey: ["provider-status"],
    queryFn: fetchProviderStatus,
  });
  const availabilityByEndpoint = useMemo(
    () => new Map((statusQuery.data?.endpoints ?? []).map((entry) => [entry.endpoint_type, entry])),
    [statusQuery.data],
  );
  const methods = useMemo(() => collectMethods(data?.packages ?? []), [data]);
  const filtered = useMemo(
    () => filterPlatformPackages(
      data?.packages ?? [],
      { query, method, status, availability },
      availabilityByEndpoint,
    ),
    [availability, availabilityByEndpoint, data, method, query, status],
  );

  function updateStatus(value: string) {
    if (
      value === "all" ||
      value === "verified" ||
      value === "pending" ||
      value === "disabled"
    ) {
      setStatus(value);
    }
  }

  function updateAvailability(value: string) {
    if (
      value === "all" || value === "verified" || value === "config-gated" ||
      value === "degraded" || value === "empty" || value === "untested" || value === "disabled"
    ) setAvailability(value);
  }

  return (
    <AppShell
      title="Skill 与 MCP 目录"
      description="按平台复用采集能力、Playbook 与共享 MCP Runtime"
      brief="所有工具包由生产 catalog 自动生成，Provider 凭据仅保留在服务端。"
    >
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="平台 Skill" value={data?.platform_count ?? 0} icon={<Box size={16} />} />
        <Metric label="唯一端点" value={data?.unique_endpoint_count ?? 0} icon={<ServerCog size={16} />} />
        <Metric label="能力视图" value={data?.capability_count ?? 0} icon={<Cable size={16} />} />
        <Metric label="共享 MCP" value={1} icon={<BookOpen size={16} />} />
      </section>
      <section className="grid gap-3 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4 md:grid-cols-2 xl:grid-cols-[1fr_12rem_12rem_12rem]">
        <label className="relative">
          <Search className="absolute left-3 top-3 text-[var(--text-tertiary)]" size={15} />
          <span className="sr-only">搜索平台与能力</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索 TikTok、Amazon、Exa 或 endpoint_type"
            className="h-10 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] pl-9 pr-3 text-sm outline-none focus:border-[var(--action-primary)]"
          />
        </label>
        <select value={method} onChange={(event) => setMethod(event.target.value)} className="h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm">
          <option value="">全部采集方式</option>
          {methods.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select value={status} onChange={(event) => updateStatus(event.target.value)} className="h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm">
          <option value="all">全部状态</option>
          <option value="verified">已验证</option>
          <option value="pending">待验证</option>
          <option value="disabled">已停用</option>
        </select>
        <select value={availability} onChange={(event) => updateAvailability(event.target.value)} className="h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-canvas)] px-3 text-sm">
          <option value="all">全部实时状态</option>
          <option value="verified">verified</option>
          <option value="config-gated">config-gated</option>
          <option value="degraded">degraded</option>
          <option value="empty">empty</option>
          <option value="untested">untested</option>
          <option value="disabled">disabled</option>
        </select>
      </section>
      {isLoading ? <State text="正在加载平台工具包…" /> : error ? <State text="Skill 目录加载失败，请检查 API。" danger /> : filtered.length === 0 ? <State text="没有匹配的平台工具包。" /> : (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((item) => <PackageCard key={item.platform_id} item={item} availability={item.endpoints.flatMap((endpoint) => { const state = availabilityByEndpoint.get(endpoint.endpoint_type); return state ? [state] : []; })} />)}
        </section>
      )}
    </AppShell>
  );
}

function Metric({ label, value, icon }: { readonly label: string; readonly value: number; readonly icon: React.ReactNode }) {
  return <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-4"><div className="flex items-center gap-2 text-xs text-[var(--text-tertiary)]">{icon}{label}</div><p className="mt-2 text-2xl font-bold tabular-nums">{value}</p></div>;
}

function State({ text, danger = false }: { readonly text: string; readonly danger?: boolean }) {
  return <div className={`rounded-[var(--radius-3)] border p-12 text-center text-sm ${danger ? "border-[var(--state-danger)] bg-[var(--danger-soft)] text-[var(--state-danger)]" : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-tertiary)]"}`}>{text}</div>;
}
