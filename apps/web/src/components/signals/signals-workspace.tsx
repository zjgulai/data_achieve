"use client";

import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BellRing,
  Braces,
  Filter,
  Gauge,
  GitCompareArrows,
  Hash,
  Radar,
  Search,
  ShieldAlert,
  Target,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { listSignals } from "@/lib/api/signals";
import { cn } from "@/lib/utils";
import type { Signal } from "@/types/signal";

type SeverityFilter = "all" | string;
type TypeFilter = "all" | string;

const severityTone: Record<
  string,
  {
    label: string;
    accent: string;
    surface: string;
    pill: string;
    text: string;
  }
> = {
  low: {
    label: "Low",
    accent: "bg-[#7D9A68]",
    surface: "border-[#D9E2CC] bg-[#F7FBF1]",
    pill: "bg-[#EFF7EC] text-[#5D7B4E]",
    text: "text-[#536B40]",
  },
  medium: {
    label: "Medium",
    accent: "bg-[#D5A642]",
    surface: "border-[#E7D8B8] bg-[#FFF9E9]",
    pill: "bg-[#FFF3D5] text-[#8C6824]",
    text: "text-[#8C6824]",
  },
  high: {
    label: "High",
    accent: "bg-[#C96F5C]",
    surface: "border-[#E8D4CB] bg-[#FFF7F2]",
    pill: "bg-[#FFF0EC] text-[#B85F4F]",
    text: "text-[#9E4F41]",
  },
  critical: {
    label: "Critical",
    accent: "bg-[#8D3F34]",
    surface: "border-[#E8C7BF] bg-[#FFF2EF]",
    pill: "bg-[#F6E7E4] text-[#8D3F34]",
    text: "text-[#8D3F34]",
  },
};

const signalTypeLabels: Record<string, string> = {
  star_growth: "Star Growth",
  page_changed: "Page Changed",
  data_quality_anomaly: "Data Quality",
};

export function SignalsWorkspace() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>("all");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");

  useEffect(() => {
    let mounted = true;
    listSignals()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setSignals(items);
        setSelectedId(items[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load signals");
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

  const selectedSignal = useMemo(() => {
    return signals.find((item) => item.id === selectedId) ?? null;
  }, [signals, selectedId]);

  const signalTypes = useMemo(() => {
    return Array.from(new Set(signals.map((signal) => signal.signalType)));
  }, [signals]);

  const severities = useMemo(() => {
    return Array.from(new Set(signals.map((signal) => signal.severity)));
  }, [signals]);

  const filteredSignals = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return signals.filter((signal) => {
      const matchesSeverity = severityFilter === "all" || signal.severity === severityFilter;
      const matchesType = typeFilter === "all" || signal.signalType === typeFilter;
      if (!matchesSeverity || !matchesType) {
        return false;
      }
      if (!term) {
        return true;
      }
      return [
        signal.id,
        signal.signalType,
        signal.entityId,
        signal.projectId,
        signal.severity,
        JSON.stringify(signal.metadata),
      ]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [searchTerm, severityFilter, signals, typeFilter]);

  const stats = useMemo(() => {
    const highRisk = signals.filter((signal) =>
      ["high", "critical"].includes(signal.severity),
    ).length;
    const averageConfidence =
      signals.length === 0
        ? 0
        : Math.round(signals.reduce((sum, signal) => sum + signal.confidence, 0) / signals.length);
    const uniqueEntities = new Set(signals.map((signal) => signal.entityId)).size;
    return {
      total: signals.length,
      highRisk,
      averageConfidence,
      uniqueEntities,
    };
  }, [signals]);

  return (
    <div className="grid min-w-0 gap-5">
      <section className="overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Radar size={14} aria-hidden="true" />
              Signal Detection Layer
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              信号检测控制台
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#7A625A]">
              把实体快照差异转成确定性信号，保留触发规则、严重度、置信度和前后快照绑定。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <MetricPill icon={Activity} label="信号数" value={String(stats.total)} />
              <MetricPill icon={ShieldAlert} label="高风险" value={String(stats.highRisk)} />
              <MetricPill icon={Gauge} label="平均置信" value={`${stats.averageConfidence}`} />
              <MetricPill icon={Target} label="影响实体" value={String(stats.uniqueEntities)} />
            </div>
          </div>

          <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Severity Mix</p>
                <h3 className="mt-1 text-base font-semibold text-[#2E201C]">严重度分布</h3>
              </div>
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#C96F5C] text-white">
                <BellRing size={18} aria-hidden="true" />
              </span>
            </div>
            <div className="mt-4 grid gap-2">
              {["critical", "high", "medium", "low"].map((severity) => (
                <SeverityRow
                  count={signals.filter((signal) => signal.severity === severity).length}
                  key={severity}
                  severity={severity}
                />
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_450px]">
        <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Signal Queue</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">变化信号队列</h2>
              <p className="mt-1 text-sm text-[#7A625A]">按信号类型、严重度和实体 ID 定位待判读变化。</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-none xl:grid-cols-3">
              <label className="relative block">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                  size={16}
                  aria-hidden="true"
                />
                <input
                  className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="搜索信号、实体、规则"
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
                  className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-8 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                  onChange={(event) => setTypeFilter(event.target.value)}
                  value={typeFilter}
                >
                  <option value="all">全部类型</option>
                  {signalTypes.map((type) => (
                    <option key={type} value={type}>
                      {formatSignalType(type)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="relative block">
                <ShieldAlert
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                  size={16}
                  aria-hidden="true"
                />
                <select
                  className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-8 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
                  onChange={(event) => setSeverityFilter(event.target.value)}
                  value={severityFilter}
                >
                  <option value="all">全部严重度</option>
                  {severities.map((severity) => (
                    <option key={severity} value={severity}>
                      {getSeverityTone(severity).label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
              加载信号中
            </div>
          ) : null}
          {error ? (
            <p className="mb-4 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
              {error}
            </p>
          ) : null}

          <div className="grid gap-3">
            {filteredSignals.map((signal) => (
              <SignalCard
                key={signal.id}
                onSelect={() => setSelectedId(signal.id)}
                selected={signal.id === selectedId}
                signal={signal}
              />
            ))}
            {!loading && filteredSignals.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                没有匹配的信号。
              </div>
            ) : null}
          </div>
        </section>

        <aside className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Signal Detail</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">信号详情</h2>
              <p className="mt-1 text-sm text-[#7A625A]">规则元数据、快照绑定和检测值。</p>
            </div>
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
              <Braces size={18} aria-hidden="true" />
            </span>
          </div>

          {selectedSignal ? <SignalDetail signal={selectedSignal} /> : <EmptyDetail />}
        </aside>
      </div>
    </div>
  );
}

function SignalCard({
  signal,
  selected,
  onSelect,
}: {
  signal: Signal;
  selected: boolean;
  onSelect: () => void;
}) {
  const tone = getSeverityTone(signal.severity);
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
              <Zap size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="break-words text-base font-semibold text-[#2E201C]">
                  {formatSignalType(signal.signalType)}
                </h3>
                <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold", tone.pill)}>
                  {tone.label}
                </span>
              </div>
              <p className="mt-1 break-all text-sm text-[#7A625A]">{signal.entityId}</p>
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-4">
            <SignalFact label="current" value={formatMaybeNumber(signal.currentValue)} />
            <SignalFact label="delta" value={formatMaybeNumber(signal.delta)} />
            <SignalFact label="ratio" value={formatRatio(signal.deltaRatio)} />
            <SignalFact label="confidence" value={`${signal.confidence}`} />
          </div>
        </div>

        <div className="flex shrink-0 flex-col gap-2 lg:w-56">
          <span className="inline-flex items-center gap-2 rounded-xl border border-white/80 bg-white/80 px-3 py-2 text-xs font-semibold text-[#7D4F43]">
            <GitCompareArrows size={14} aria-hidden="true" />
            {signal.previousSnapshotId} → {signal.currentSnapshotId}
          </span>
          <span className="inline-flex items-center gap-2 rounded-xl border border-white/80 bg-white/80 px-3 py-2 text-xs font-semibold text-[#7D4F43]">
            <Hash size={14} aria-hidden="true" />
            {formatDate(signal.detectedAt)}
          </span>
        </div>
      </div>
    </button>
  );
}

function SignalDetail({ signal }: { signal: Signal }) {
  const tone = getSeverityTone(signal.severity);
  const metadataText = JSON.stringify(signal.metadata, null, 2);
  return (
    <div className="grid gap-4">
      <div className={cn("rounded-2xl border p-4", tone.surface)}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={cn("text-xs font-semibold uppercase", tone.text)}>
              {formatSignalType(signal.signalType)}
            </p>
            <h3 className="mt-1 break-words text-lg font-semibold text-[#2E201C]">
              {tone.label} severity signal
            </h3>
            <p className="mt-1 text-sm text-[#7A625A]">{formatDate(signal.detectedAt)}</p>
          </div>
          <span
            className={cn(
              "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white",
              tone.accent,
            )}
          >
            <ShieldAlert size={18} aria-hidden="true" />
          </span>
        </div>
        <div className="mt-4 grid gap-2">
          <DetailRow label="Signal ID" value={signal.id} />
          <DetailRow label="Entity ID" value={signal.entityId} />
          <DetailRow label="Project" value={signal.projectId} />
        </div>
      </div>

      <section className="rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-3">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase text-[#B47767]">Snapshot Binding</p>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#7D4F43]">
            deterministic
          </span>
        </div>
        <div className="grid gap-2">
          <CompareRow label="Previous" value={signal.previousSnapshotId} />
          <CompareRow label="Current" value={signal.currentSnapshotId} />
        </div>
      </section>

      <section className="grid grid-cols-2 gap-2">
        <ScoreCard label="previous" value={formatMaybeNumber(signal.previousValue)} />
        <ScoreCard label="current" value={formatMaybeNumber(signal.currentValue)} />
        <ScoreCard label="delta" value={formatMaybeNumber(signal.delta)} />
        <ScoreCard label="ratio" value={formatRatio(signal.deltaRatio)} />
      </section>

      <div className="rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-3">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase text-[#B47767]">Rule Metadata</p>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#7D4F43]">
            {metadataText.length} chars
          </span>
        </div>
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-xl bg-[#2E201C] p-4 text-xs leading-5 text-[#FFF8F4]">
          {metadataText}
        </pre>
      </div>
    </div>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Activity;
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

function SeverityRow({ severity, count }: { severity: string; count: number }) {
  const tone = getSeverityTone(severity);
  return (
    <div className="flex items-center justify-between rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2">
      <span className="inline-flex items-center gap-2 text-sm font-medium text-[#3B2924]">
        <span className={cn("h-2.5 w-2.5 rounded-full", tone.accent)} />
        {tone.label}
      </span>
      <span className="text-sm font-semibold text-[#3B2924]">{count}</span>
    </div>
  );
}

function SignalFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-xl border border-white/80 bg-white/70 px-3 py-2">
      <p className="text-xs font-semibold text-[#B47767]">{label}</p>
      <p className="mt-1 flex items-center gap-1 break-words text-sm font-semibold leading-5 text-[#3B2924]">
        {value}
        {label === "delta" ? <DeltaIcon value={value} /> : null}
      </p>
    </div>
  );
}

function ScoreCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 py-3">
      <p className="text-xs font-semibold uppercase text-[#B47767]">{label}</p>
      <p className="mt-2 flex items-center gap-1 text-lg font-semibold text-[#2E201C]">
        {value}
        {label === "delta" ? <DeltaIcon value={value} /> : null}
      </p>
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

function CompareRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-[#F0E1D9] bg-white/80 px-3 py-2">
      <span className="text-sm font-semibold text-[#7A625A]">{label}</span>
      <span className="break-all text-right text-sm font-semibold text-[#3B2924]">{value}</span>
    </div>
  );
}

function EmptyDetail() {
  return (
    <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
      选择一条信号查看详情。
    </div>
  );
}

function DeltaIcon({ value }: { value: string }) {
  const numberValue = Number(value);
  if (Number.isNaN(numberValue) || numberValue === 0) {
    return null;
  }
  return numberValue > 0 ? (
    <ArrowUpRight size={14} aria-hidden="true" />
  ) : (
    <ArrowDownRight size={14} aria-hidden="true" />
  );
}

function getSeverityTone(severity: string) {
  return (
    severityTone[severity] ?? {
      label: severity,
      accent: "bg-[#B47767]",
      surface: "border-[#E8D4CB] bg-[#FFF8F4]",
      pill: "bg-[#F6ECE8] text-[#7D4F43]",
      text: "text-[#9E5C4D]",
    }
  );
}

function formatSignalType(type: string): string {
  return signalTypeLabels[type] ?? type.split("_").map(capitalize).join(" ");
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatMaybeNumber(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function formatRatio(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `${Math.round(value * 100)}%`;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
