"use client";

import {
  Activity,
  Boxes,
  ExternalLink,
  Filter,
  Fingerprint,
  Globe2,
  Layers3,
  Link2,
  PackageSearch,
  Radar,
  Search,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listEntities, listEntitySnapshots } from "@/lib/api/entities";
import { listEntitySignals } from "@/lib/api/signals";
import { buildAuditFacts, getAuditFactCount, type AuditFact } from "@/lib/audit-display";
import { cn } from "@/lib/utils";
import type { Entity, EntitySnapshot } from "@/types/entity";
import type { Signal } from "@/types/signal";

type DomainFilter = "all" | string;

const domainTone: Record<
  string,
  {
    label: string;
    accent: string;
    surface: string;
    text: string;
  }
> = {
  osint: {
    label: "开源雷达",
    accent: "bg-[#C96F5C]",
    surface: "border-[#E8D4CB] bg-[#FFF7F2]",
    text: "text-[#9E4F41]",
  },
  ecommerce: {
    label: "电商风向",
    accent: "bg-[#D5A642]",
    surface: "border-[#E7D8B8] bg-[#FFF9E9]",
    text: "text-[#8C6824]",
  },
  social: {
    label: "社媒脉搏",
    accent: "bg-[#8D75A8]",
    surface: "border-[#DFD5E8] bg-[#FAF6FF]",
    text: "text-[#6B5685]",
  },
  competitor: {
    label: "竞品守望",
    accent: "bg-[#7D9A68]",
    surface: "border-[#D9E2CC] bg-[#F7FBF1]",
    text: "text-[#536B40]",
  },
  mixed: {
    label: "混合项目",
    accent: "bg-[#B47767]",
    surface: "border-[#E8D4CB] bg-[#FFF8F4]",
    text: "text-[#9E5C4D]",
  },
};

const severityTone: Record<string, string> = {
  low: "bg-[#EFF7EC] text-[#5D7B4E]",
  medium: "bg-[#FFF3D5] text-[#8C6824]",
  high: "bg-[#FFF0EC] text-[#B85F4F]",
  critical: "bg-[#F6E7E4] text-[#8D3F34]",
};

export function EntitiesWorkspace() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [snapshots, setSnapshots] = useState<EntitySnapshot[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [snapshotsLoading, setSnapshotsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [domainFilter, setDomainFilter] = useState<DomainFilter>("all");

  useEffect(() => {
    let mounted = true;
    listEntities()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setEntities(items);
        setSelectedId(items[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load entities");
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
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setSnapshots([]);
      setSignals([]);
      return;
    }
    let mounted = true;
    setSnapshotsLoading(true);
    Promise.all([listEntitySnapshots(selectedId), listEntitySignals(selectedId)])
      .then(([snapshotItems, signalItems]) => {
        if (mounted) {
          setSnapshots(snapshotItems);
          setSignals(signalItems);
        }
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load snapshots");
        }
      })
      .finally(() => {
        if (mounted) {
          setSnapshotsLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [selectedId]);

  const selectedEntity = useMemo(() => {
    return entities.find((item) => item.id === selectedId) ?? null;
  }, [entities, selectedId]);

  const domains = useMemo(() => {
    return Array.from(new Set(entities.map((entity) => entity.domain)));
  }, [entities]);

  const filteredEntities = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return entities.filter((entity) => {
      const matchesDomain = domainFilter === "all" || entity.domain === domainFilter;
      if (!matchesDomain) {
        return false;
      }
      if (!term) {
        return true;
      }
      return [entity.name, entity.externalId, entity.entityType, entity.domain, entity.projectId]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [domainFilter, entities, searchTerm]);

  const stats = useMemo(() => {
    const typedEntities = new Set(entities.map((entity) => entity.entityType)).size;
    const linkedEntities = entities.filter((entity) => Boolean(entity.canonicalUrl)).length;
    const activeDomains = new Set(entities.map((entity) => entity.domain)).size;
    return {
      total: entities.length,
      typedEntities,
      linkedEntities,
      activeDomains,
    };
  }, [entities]);

  const latestSnapshot = snapshots[0] ?? null;

  return (
    <div className="grid min-w-0 gap-5">
      <section className="overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Boxes size={14} aria-hidden="true" />
              Entity Snapshot Layer
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              实体快照工作台
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#7A625A]">
              把采集事实标准化为可持续追踪的实体画像，保留快照指标、来源批次和触发信号。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <MetricPill icon={PackageSearch} label="实体数" value={String(stats.total)} />
              <MetricPill icon={Layers3} label="类型数" value={String(stats.typedEntities)} />
              <MetricPill icon={Globe2} label="链接实体" value={String(stats.linkedEntities)} />
              <MetricPill icon={Radar} label="覆盖域" value={String(stats.activeDomains)} />
            </div>
          </div>

          <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Selected Entity</p>
                <h3 className="mt-1 text-base font-semibold text-[#2E201C]">
                  {selectedEntity?.name ?? "尚未选择"}
                </h3>
              </div>
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#C96F5C] text-white">
                <ShieldCheck size={18} aria-hidden="true" />
              </span>
            </div>
            <div className="mt-4 grid gap-2">
              <IntegrityRow label="快照数" value={String(snapshots.length)} />
              <IntegrityRow label="关联信号" value={String(signals.length)} />
              <IntegrityRow
                label="最新采集"
                value={latestSnapshot ? formatDate(latestSnapshot.capturedAt) : "—"}
              />
            </div>
          </div>
        </div>
      </section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_470px]">
        <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Entity Registry</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">标准化实体库</h2>
              <p className="mt-1 text-sm text-[#7A625A]">按业务域、类型和外部 ID 定位持续追踪对象。</p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <label className="relative block">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                  size={16}
                  aria-hidden="true"
                />
                <input
                  className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE] sm:w-60"
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="搜索实体、外部 ID"
                  value={searchTerm}
                />
              </label>
              <label className="relative block">
                <Filter
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                  size={16}
                  aria-hidden="true"
                />
                <select
                  className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-8 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE] sm:w-40"
                  onChange={(event) => setDomainFilter(event.target.value)}
                  value={domainFilter}
                >
                  <option value="all">全部业务域</option>
                  {domains.map((domain) => (
                    <option key={domain} value={domain}>
                      {getDomainTone(domain).label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
              加载实体中
            </div>
          ) : null}
          {error ? (
            <p className="mb-4 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
              {error}
            </p>
          ) : null}

          <div className="grid gap-3">
            {filteredEntities.map((entity) => (
              <EntityCard
                entity={entity}
                key={entity.id}
                onSelect={() => setSelectedId(entity.id)}
                selected={entity.id === selectedId}
              />
            ))}
            {!loading && filteredEntities.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                没有匹配的实体。
              </div>
            ) : null}
          </div>
        </section>

        <aside className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Snapshot Timeline</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">快照时间线</h2>
              <p className="mt-1 text-sm text-[#7A625A]">指标、采集来源和关联信号。</p>
            </div>
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
              <Layers3 size={18} aria-hidden="true" />
            </span>
          </div>

          {selectedEntity ? (
            <EntityDetail
              entity={selectedEntity}
              signals={signals}
              snapshots={snapshots}
              snapshotsLoading={snapshotsLoading}
            />
          ) : (
            <EmptyDetail />
          )}
        </aside>
      </div>
    </div>
  );
}

function EntityCard({
  entity,
  selected,
  onSelect,
}: {
  entity: Entity;
  selected: boolean;
  onSelect: () => void;
}) {
  const tone = getDomainTone(entity.domain);
  return (
    <button
      className={cn(
        "rounded-2xl border p-4 text-left transition hover:-translate-y-0.5 hover:shadow-[0_14px_36px_rgba(72,45,38,0.1)]",
        tone.surface,
        selected ? "ring-2 ring-[#C96F5C] ring-offset-2 ring-offset-white" : "",
      )}
      onClick={onSelect}
      type="button"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className={cn(
                "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-white",
                tone.accent,
              )}
            >
              <Boxes size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="break-words text-base font-semibold text-[#2E201C]">{entity.name}</h3>
                <span className={cn("rounded-full bg-white/80 px-2.5 py-1 text-xs font-semibold", tone.text)}>
                  {tone.label}
                </span>
              </div>
              <p className="mt-1 break-all text-sm text-[#7A625A]">{entity.externalId}</p>
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <EntityFact label="类型" value={formatEntityType(entity.entityType)} />
            <EntityFact label="首次发现" value={formatDate(entity.firstSeenAt)} />
            <EntityFact label="最近出现" value={formatDate(entity.lastSeenAt)} />
          </div>
        </div>

        <div className="flex shrink-0 flex-col gap-2 lg:w-52">
          <span className="inline-flex items-center gap-2 rounded-xl border border-white/80 bg-white/80 px-3 py-2 text-xs font-semibold text-[#7D4F43]">
            <Fingerprint size={14} aria-hidden="true" />
            {entity.latestSnapshotId ?? "no snapshot"}
          </span>
          <span className="inline-flex items-center gap-2 rounded-xl border border-white/80 bg-white/80 px-3 py-2 text-xs font-semibold text-[#7D4F43]">
            <Link2 size={14} aria-hidden="true" />
            {entity.canonicalUrl ? "canonical link" : "no link"}
          </span>
        </div>
      </div>
    </button>
  );
}

function EntityDetail({
  entity,
  snapshots,
  signals,
  snapshotsLoading,
}: {
  entity: Entity;
  snapshots: EntitySnapshot[];
  signals: Signal[];
  snapshotsLoading: boolean;
}) {
  const tone = getDomainTone(entity.domain);
  return (
    <div className="grid gap-4">
      <div className={cn("rounded-2xl border p-4", tone.surface)}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={cn("text-xs font-semibold uppercase", tone.text)}>{tone.label}</p>
            <h3 className="mt-1 break-words text-lg font-semibold text-[#2E201C]">{entity.name}</h3>
            <p className="mt-1 break-all text-sm text-[#7A625A]">{entity.externalId}</p>
          </div>
          <span
            className={cn(
              "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white",
              tone.accent,
            )}
          >
            <Boxes size={18} aria-hidden="true" />
          </span>
        </div>
        <div className="mt-4 grid gap-2">
          <DetailRow label="实体批次" value={formatShortTraceId(entity.id)} />
          <DetailRow label="所属项目" value={formatShortTraceId(entity.projectId)} />
          <DetailRow label="最新快照" value={formatShortTraceId(entity.latestSnapshotId)} />
        </div>
      </div>

      {entity.canonicalUrl ? (
        <a
          className="inline-flex items-center gap-2 break-all rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 py-2 text-sm font-semibold text-[#9E5C4D] transition hover:border-[#C96F5C] hover:text-[#B85F4F]"
          href={entity.canonicalUrl}
          rel="noreferrer"
          target="_blank"
        >
          <ExternalLink size={16} aria-hidden="true" />
          {entity.canonicalUrl}
        </a>
      ) : null}

      <section className="rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-3">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase text-[#B47767]">Related Signals</p>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#7D4F43]">
            {signals.length}
          </span>
        </div>
        <div className="grid gap-2">
          {signals.map((signal) => (
            <SignalRow key={signal.id} signal={signal} />
          ))}
          {signals.length === 0 ? (
            <p className="rounded-xl border border-dashed border-[#E8D4CB] bg-white/70 px-3 py-3 text-sm text-[#7A625A]">
              暂无关联信号。
            </p>
          ) : null}
        </div>
      </section>

      <section className="grid gap-3">
        {snapshotsLoading ? (
          <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-6 text-sm text-[#7A625A]">
            加载快照中
          </div>
        ) : (
          snapshots.map((snapshot, index) => (
            <SnapshotCard
              key={snapshot.id}
              latest={index === 0}
              snapshot={snapshot}
            />
          ))
        )}
        {!snapshotsLoading && snapshots.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-6 text-sm text-[#7A625A]">
            暂无快照。
          </div>
        ) : null}
      </section>
    </div>
  );
}

function SignalRow({ signal }: { signal: Signal }) {
  return (
    <div className="rounded-xl border border-[#F0E1D9] bg-white/80 px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-[#2E201C]">{signal.signalType}</p>
          <p className="mt-1 text-xs text-[#7A625A]">{formatDate(signal.detectedAt)}</p>
        </div>
        <span
          className={cn(
            "rounded-full px-2.5 py-1 text-xs font-semibold",
            severityTone[signal.severity] ?? "bg-[#F6ECE8] text-[#7D4F43]",
          )}
        >
          {signal.severity}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <MiniFact label="current" value={formatMaybeNumber(signal.currentValue)} />
        <MiniFact label="delta" value={formatMaybeNumber(signal.delta)} />
        <MiniFact label="confidence" value={`${signal.confidence}`} />
      </div>
    </div>
  );
}

function SnapshotCard({ snapshot, latest }: { snapshot: EntitySnapshot; latest: boolean }) {
  const snapshotFacts = buildAuditFacts(snapshot.snapshotData, 8);
  const factCount = getAuditFactCount(snapshot.snapshotData);
  return (
    <article className="rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-[#2E201C]">{formatDate(snapshot.capturedAt)}</h3>
            {latest ? (
              <span className="rounded-full bg-[#ECF7EA] px-2.5 py-1 text-xs font-semibold text-[#4E7C45]">
                latest
              </span>
            ) : null}
          </div>
          <p className="mt-1 break-all text-xs text-[#7A625A]">
            来源批次 {formatShortTraceId(snapshot.rawRecordId)}
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-xl bg-[#FFF7F2] px-3 py-2 text-xs font-semibold text-[#9E5C4D]">
          <Activity size={14} aria-hidden="true" />
          {Object.keys(snapshot.metrics).length} metrics / {factCount} facts
        </span>
      </div>
      <MetricGrid metrics={snapshot.metrics} />
      <FactGrid facts={snapshotFacts} emptyText="没有可展示的业务快照字段。" />
    </article>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof PackageSearch;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 px-4 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase text-[#B47767]">
        <Icon size={14} aria-hidden="true" />
        {label}
      </div>
      <p className="mt-2 break-words text-xl font-semibold text-[#2E201C]">{value}</p>
    </div>
  );
}

function IntegrityRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      <span className="text-sm font-medium text-[#7A625A]">{label}</span>
      <span className="text-sm font-semibold text-[#3B2924]">{value}</span>
    </div>
  );
}

function EntityFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/80 bg-white/70 px-3 py-2">
      <p className="text-xs font-semibold text-[#B47767]">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold leading-5 text-[#3B2924]">{value}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/80 bg-white/75 px-3 py-2 text-sm">
      <span className="text-xs font-semibold uppercase text-[#B47767]">{label}</span>
      <p className="mt-1 break-all font-semibold text-[#3B2924]">{value}</p>
    </div>
  );
}

function MetricGrid({ metrics }: { metrics: Record<string, unknown> }) {
  const entries = Object.entries(metrics).filter(([, value]) => value !== null);
  if (entries.length === 0) {
    return null;
  }
  return (
    <div className="mt-3 grid grid-cols-2 gap-2">
      {entries.map(([key, value]) => (
        <div className="rounded-xl border border-[#F0E1D9] bg-[#FFF8F4] px-3 py-2 text-xs" key={key}>
          <span className="text-[#B47767]">{key}</span>
          <p className="mt-1 break-words font-semibold text-[#3B2924]">{String(value)}</p>
        </div>
      ))}
    </div>
  );
}

function FactGrid({
  facts,
  emptyText,
}: {
  facts: AuditFact[];
  emptyText: string;
}) {
  if (facts.length === 0) {
    return (
      <p className="mt-3 rounded-xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] px-3 py-3 text-sm text-[#7A625A]">
        {emptyText}
      </p>
    );
  }
  return (
    <div className="mt-3 grid grid-cols-2 gap-2">
      {facts.map((fact) => (
        <div
          className="rounded-xl border border-[#F0E1D9] bg-[#FFF8F4] px-3 py-2 text-xs"
          key={`${fact.label}-${fact.value}`}
        >
          <span className="text-[#B47767]">{fact.label}</span>
          <p className="mt-1 break-words font-semibold text-[#3B2924]">{fact.value}</p>
        </div>
      ))}
    </div>
  );
}

function MiniFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[#FFF8F4] px-2 py-1.5">
      <p className="text-[11px] font-semibold uppercase text-[#B47767]">{label}</p>
      <p className="mt-1 text-xs font-semibold text-[#3B2924]">{value}</p>
    </div>
  );
}

function EmptyDetail() {
  return (
    <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
      选择一个实体查看快照。
    </div>
  );
}

function getDomainTone(domain: string) {
  return domainTone[domain] ?? domainTone.mixed;
}

function formatMaybeNumber(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function formatEntityType(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatShortTraceId(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return value.length > 12 ? `${value.slice(0, 8)}...` : value;
}
