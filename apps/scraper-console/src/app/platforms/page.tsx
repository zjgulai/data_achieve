"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { QuickCollectDrawer } from "@/components/platforms/quick-collect-drawer";
import { fetchCollectorCatalog } from "@/lib/api/collectors";
import type { CollectorEntry, CollectorEndpoint } from "@/lib/api/collectors";

/* ── Status badge ── */
function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    verified: "bg-[var(--success-soft)] text-[var(--state-success)] border-[var(--state-success)]",
    pending:  "bg-[var(--warning-soft)] text-[var(--state-warning)] border-[var(--state-warning)]",
    disabled: "bg-[var(--danger-soft)]  text-[var(--state-danger)]  border-[var(--state-danger)]",
  };
  const labels: Record<string, string> = {
    verified: "已验证",
    pending:  "待验证",
    disabled: "已禁用",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
        styles[status] ?? styles.disabled
      }`}
    >
      {labels[status] ?? status}
    </span>
  );
}

/* ── Collector card ── */
function CollectorCard({
  endpoint,
  onCollect,
}: {
  endpoint: CollectorEndpoint;
  onCollect: (ep: CollectorEndpoint) => void;
}) {
  return (
    <div className="flex flex-col rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5 transition-shadow duration-[var(--duration-base)] hover:shadow-[var(--shadow-overlay)]">
      <div className="flex items-start justify-between">
        <h3 className="text-base font-semibold text-[var(--text-primary)]">
          {endpoint.label}
        </h3>
        <StatusBadge status={endpoint.status} />
      </div>

      <p className="mt-1 text-xs text-[var(--text-tertiary)]">{endpoint.provider}</p>
      <p className="mt-3 flex-1 text-sm leading-relaxed text-[var(--text-secondary)]">
        {endpoint.description}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {endpoint.cost_hint && (
          <span className="inline-flex items-center rounded-[var(--radius-1)] bg-[var(--accent-2-soft)] px-2 py-1 text-xs font-medium text-[var(--state-info)]">
            💰 {endpoint.cost_hint}
          </span>
        )}
        <span className="inline-flex items-center rounded-[var(--radius-1)] bg-[var(--surface-muted)] px-2 py-1 text-xs font-medium text-[var(--text-tertiary)]">
          {endpoint.platform}
        </span>
        {endpoint.required_params.length > 0 && (
          <span className="inline-flex items-center rounded-[var(--radius-1)] bg-[var(--surface-muted)] px-2 py-1 text-xs font-medium text-[var(--text-tertiary)]">
            必填: {endpoint.required_params.join(", ")}
          </span>
        )}
      </div>

      {endpoint.status === "verified" && (
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => onCollect(endpoint)}
            className="flex-1 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] transition-colors duration-[var(--duration-base)] hover:bg-[var(--action-primary-hover)]"
          >
            ▶ 快速采集
          </button>
        </div>
      )}

      {endpoint.status === "pending" && (
        <p className="mt-4 text-xs text-[var(--text-tertiary)]">
          正在验证，暂不可用
        </p>
      )}
    </div>
  );
}

/* ── Platform section ── */
function PlatformSection({
  collector,
  onCollect,
}: {
  collector: CollectorEntry;
  onCollect: (ep: CollectorEndpoint) => void;
}) {
  const available = collector.endpoints.filter((e) => e.status !== "disabled");
  if (available.length === 0) return null;
  return (
    <section>
      <h2 className="mb-4 text-lg font-bold text-[var(--text-primary)]">
        {collector.label}
        <span className="ml-2 text-sm font-normal text-[var(--text-tertiary)]">
          {available.length} 个能力
        </span>
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {available.map((endpoint) => (
          <CollectorCard
            key={endpoint.endpoint_type}
            endpoint={endpoint}
            onCollect={onCollect}
          />
        ))}
      </div>
    </section>
  );
}

/* ── Page ── */
export default function PlatformsPage() {
  const [activeEndpoint, setActiveEndpoint] = useState<CollectorEndpoint | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["collector-catalog"],
    queryFn: fetchCollectorCatalog,
  });

  return (
    <AppShell
      title="平台能力中心"
      description="所有已验证的数据采集能力"
      brief="点击「快速采集」立即启动数据采集任务，无需配置复杂的采集源"
    >
      {isLoading ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-8 text-center">
          <p className="text-sm text-[var(--text-tertiary)]">加载中...</p>
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-8 text-center">
          <p className="text-sm text-[var(--state-danger)]">
            后端未连接，请先启动 API 服务
          </p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">
            {(error as Error).message}
          </p>
        </div>
      ) : (
        <div className="grid gap-8">
          {data?.collectors.map((collector) => (
            <PlatformSection
              key={collector.collector_type}
              collector={collector}
              onCollect={setActiveEndpoint}
            />
          ))}
        </div>
      )}

      {activeEndpoint && (
        <QuickCollectDrawer
          endpoint={activeEndpoint}
          open={!!activeEndpoint}
          onClose={() => setActiveEndpoint(null)}
        />
      )}
    </AppShell>
  );
}
