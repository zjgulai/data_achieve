"use client";

import {
  Braces,
  Camera,
  Clock3,
  Database,
  FileJson2,
  Filter,
  Fingerprint,
  Globe2,
  Hash,
  Link2,
  Search,
  ShieldCheck,
} from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";

import { listRawRecords } from "@/lib/api/raw-records";
import { buildAuditFacts, getAuditFactCount, type AuditFact } from "@/lib/audit-display";
import { cn } from "@/lib/utils";
import type { RawRecord } from "@/types/raw-record";

type RecordFilter = "all" | string;

const recordTypeTone: Record<
  string,
  {
    label: string;
    accent: string;
    surface: string;
    text: string;
  }
> = {
  github_repo: {
    label: "GitHub Repo",
    accent: "bg-[#C96F5C]",
    surface: "border-[#E8D4CB] bg-[#FFF7F2]",
    text: "text-[#9E4F41]",
  },
  github_topic: {
    label: "GitHub Topic",
    accent: "bg-[#D5A642]",
    surface: "border-[#E7D8B8] bg-[#FFF9E9]",
    text: "text-[#8C6824]",
  },
  generic_web: {
    label: "Generic Web",
    accent: "bg-[#7D9A68]",
    surface: "border-[#D9E2CC] bg-[#F7FBF1]",
    text: "text-[#536B40]",
  },
  manual_json: {
    label: "Manual JSON",
    accent: "bg-[#8D75A8]",
    surface: "border-[#DFD5E8] bg-[#FAF6FF]",
    text: "text-[#6B5685]",
  },
};

export function RawRecordsWorkspace() {
  const [rawRecords, setRawRecords] = useState<RawRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [recordFilter, setRecordFilter] = useState<RecordFilter>("all");

  useEffect(() => {
    let mounted = true;
    listRawRecords()
      .then((items) => {
        if (!mounted) {
          return;
        }
        setRawRecords(items);
        setSelectedId(items[0]?.id ?? null);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : "Failed to load raw records");
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

  const selectedRecord = useMemo(() => {
    return rawRecords.find((item) => item.id === selectedId) ?? null;
  }, [rawRecords, selectedId]);

  const recordTypes = useMemo(() => {
    return Array.from(new Set(rawRecords.map((record) => record.recordType)));
  }, [rawRecords]);

  const filteredRecords = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return rawRecords.filter((record) => {
      const matchesType = recordFilter === "all" || record.recordType === recordFilter;
      if (!matchesType) {
        return false;
      }
      if (!term) {
        return true;
      }
      return [
        record.id,
        record.recordType,
        record.sourceId,
        record.taskRunId,
        record.sourceUrl ?? "",
        record.contentHash,
        JSON.stringify(record.content),
      ]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [rawRecords, recordFilter, searchTerm]);

  const stats = useMemo(() => {
    const uniqueSources = new Set(rawRecords.map((record) => record.sourceId)).size;
    const withScreenshots = rawRecords.filter((record) => Boolean(record.screenshotUrl)).length;
    const latest = rawRecords
      .map((record) => new Date(record.collectedAt).getTime())
      .sort((a, b) => b - a)[0];
    return {
      total: rawRecords.length,
      uniqueSources,
      withScreenshots,
      latest: latest ? formatDate(new Date(latest).toISOString()) : "—",
    };
  }, [rawRecords]);

  return (
    <div className="grid min-w-0 gap-5">
      <section className="overflow-hidden rounded-2xl border border-[#EDDCD3] bg-[#FFF8F4] shadow-[0_18px_60px_rgba(115,70,58,0.08)]">
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E8D4CB] bg-white/75 px-3 py-1 text-xs font-semibold text-[#9E5C4D]">
              <Database size={14} aria-hidden="true" />
              事实证据层
            </div>
            <h2 className="mt-4 text-2xl font-semibold tracking-normal text-[#2E201C] sm:text-3xl">
              原始事实层审计台
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#7A625A]">
              每条原始事实都保留来源、采集时间和可校验指纹，用于回看实体、信号、证据的事实出处。
            </p>
            <div className="mt-5 grid gap-3 sm:grid-cols-4">
              <MetricPill icon={FileJson2} label="记录数" value={String(stats.total)} />
              <MetricPill icon={Globe2} label="来源数" value={String(stats.uniqueSources)} />
              <MetricPill icon={Camera} label="截图" value={String(stats.withScreenshots)} />
              <MetricPill icon={Clock3} label="最近采集" value={stats.latest} />
            </div>
          </div>

          <div className="rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase text-[#B47767]">Integrity</p>
                <h3 className="mt-1 text-base font-semibold text-[#2E201C]">证据完整性</h3>
              </div>
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-[#C96F5C] text-white">
                <ShieldCheck size={18} aria-hidden="true" />
              </span>
            </div>
            <div className="mt-4 grid gap-2">
              <IntegrityRow label="校验覆盖" value={`${rawRecords.length}/${rawRecords.length}`} />
              <IntegrityRow label="可追溯采集" value={`${rawRecords.length}/${rawRecords.length}`} />
              <IntegrityRow label="可回看来源" value={`${rawRecords.filter((record) => record.sourceUrl).length}`} />
            </div>
          </div>
        </div>
      </section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_460px]">
        <section className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Fact Records</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">采集原始记录</h2>
              <p className="mt-1 text-sm text-[#7A625A]">按类型、校验指纹、来源和采集时间定位可审计事实。</p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <label className="relative block">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#B49A91]"
                  size={16}
                  aria-hidden="true"
                />
                <input
                  className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-3 text-sm text-[#3B2924] outline-none transition placeholder:text-[#B9A19A] focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE] sm:w-64"
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="搜索标题、来源、字段"
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
                  className="h-10 w-full rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] pl-9 pr-8 text-sm text-[#3B2924] outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE] sm:w-44"
                  onChange={(event) => setRecordFilter(event.target.value)}
                  value={recordFilter}
                >
                  <option value="all">全部类型</option>
                  {recordTypes.map((type) => (
                    <option key={type} value={type}>
                      {getRecordTone(type).label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          {loading ? (
            <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
              加载原始记录中
            </div>
          ) : null}
          {error ? (
            <p className="mb-4 rounded-xl border border-[#F0C8C0] bg-[#FFF2EF] px-3 py-2 text-sm font-medium text-[#B85F4F]">
              {error}
            </p>
          ) : null}

          <div className="grid gap-3">
            {filteredRecords.map((rawRecord) => (
              <RawRecordCard
                key={rawRecord.id}
                onSelect={() => setSelectedId(rawRecord.id)}
                rawRecord={rawRecord}
                selected={rawRecord.id === selectedId}
              />
            ))}
            {!loading && filteredRecords.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
                没有匹配的原始事实。
              </div>
            ) : null}
          </div>
        </section>

        <aside className="min-w-0 rounded-2xl border border-[#EDDCD3] bg-white p-4 shadow-[0_16px_48px_rgba(72,45,38,0.07)] sm:p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase text-[#B47767]">Record Detail</p>
              <h2 className="mt-1 text-lg font-semibold text-[#2E201C]">记录详情</h2>
              <p className="mt-1 text-sm text-[#7A625A]">事实字段、来源和校验摘要</p>
            </div>
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#C96F5C] text-white">
              <Braces size={18} aria-hidden="true" />
            </span>
          </div>

          {selectedRecord ? <RecordDetail rawRecord={selectedRecord} /> : <EmptyDetail />}
        </aside>
      </div>
    </div>
  );
}

function RawRecordCard({
  rawRecord,
  selected,
  onSelect,
}: {
  rawRecord: RawRecord;
  selected: boolean;
  onSelect: () => void;
}) {
  const tone = getRecordTone(rawRecord.recordType);
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
              <FileJson2 size={18} aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="break-words text-base font-semibold text-[#2E201C]">
                  {getRecordHeadline(rawRecord)}
                </h3>
                <span className={cn("rounded-full bg-white/80 px-2.5 py-1 text-xs font-semibold", tone.text)}>
                  {tone.label}
                </span>
              </div>
              <p className="mt-1 break-all text-sm text-[#7A625A]">{getSourceLabel(rawRecord)}</p>
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <RecordFact label="采集时间" value={formatDate(rawRecord.collectedAt)} />
            <RecordFact label="事实字段" value={`${getAuditFactCount(rawRecord.content)} fields`} />
            <RecordFact label="内容大小" value={`${getContentSize(rawRecord.content)} chars`} />
          </div>
        </div>

        <div className="flex shrink-0 flex-col gap-2 lg:w-52">
          <span className="inline-flex items-center gap-2 rounded-xl border border-white/80 bg-white/80 px-3 py-2 text-xs font-semibold text-[#7D4F43]">
            <Hash size={14} aria-hidden="true" />
            校验已记录
          </span>
          <span className="inline-flex items-center gap-2 rounded-xl border border-white/80 bg-white/80 px-3 py-2 text-xs font-semibold text-[#7D4F43]">
            <Fingerprint size={14} aria-hidden="true" />
            可追溯采集
          </span>
        </div>
      </div>
    </button>
  );
}

function RecordDetail({ rawRecord }: { rawRecord: RawRecord }) {
  const tone = getRecordTone(rawRecord.recordType);
  const facts = buildAuditFacts(rawRecord.content, 14);
  const contentSize = getContentSize(rawRecord.content);

  return (
    <div className="grid gap-4">
      <div className={cn("rounded-2xl border p-4", tone.surface)}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className={cn("text-xs font-semibold uppercase", tone.text)}>{tone.label}</p>
            <h3 className="mt-1 break-words text-lg font-semibold text-[#2E201C]">
              {getRecordHeadline(rawRecord)}
            </h3>
          </div>
          <span
            className={cn(
              "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white",
              tone.accent,
            )}
          >
            <FileJson2 size={18} aria-hidden="true" />
          </span>
        </div>
        <div className="mt-4 grid gap-2">
          <DetailRow label="采集类型" value={tone.label} />
          <DetailRow label="采集时间" value={formatDate(rawRecord.collectedAt)} />
          <DetailRow label="事实字段" value={`${facts.length} fields`} />
          <DetailRow label="内容大小" value={`${contentSize} chars`} />
        </div>
      </div>

      {rawRecord.sourceUrl ? (
        <a
          className="inline-flex items-center gap-2 break-all rounded-xl border border-[#E8D4CB] bg-[#FFFDFC] px-3 py-2 text-sm font-semibold text-[#9E5C4D] transition hover:border-[#C96F5C] hover:text-[#B85F4F]"
          href={rawRecord.sourceUrl}
          rel="noreferrer"
          target="_blank"
        >
          <Link2 size={16} aria-hidden="true" />
          {rawRecord.sourceUrl}
        </a>
      ) : null}

      {rawRecord.screenshotUrl ? (
        <div className="overflow-hidden rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4]">
          <Image
            alt={`${rawRecord.id} screenshot`}
            className="h-auto w-full object-cover"
            height={520}
            priority
            src={rawRecord.screenshotUrl}
            unoptimized
            width={900}
          />
        </div>
      ) : null}

      <div className="rounded-2xl border border-[#E8D4CB] bg-[#FFF8F4] p-3">
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase text-[#B47767]">关键事实字段</p>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#7D4F43]">
            {facts.length} fields
          </span>
        </div>
        {facts.length > 0 ? <FactGrid facts={facts} /> : <EmptyFacts />}
      </div>
    </div>
  );
}

function FactGrid({ facts }: { facts: AuditFact[] }) {
  return (
    <div className="grid gap-2">
      {facts.map((fact) => (
        <DetailRow key={`${fact.label}-${fact.value}`} label={fact.label} value={fact.value} />
      ))}
    </div>
  );
}

function EmptyFacts() {
  return (
    <div className="rounded-xl border border-dashed border-[#E8D4CB] bg-[#FFFDFC] px-3 py-4 text-sm text-[#7A625A]">
      暂无可读事实字段。
    </div>
  );
}

function MetricPill({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof FileJson2;
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

function RecordFact({ label, value }: { label: string; value: string }) {
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

function EmptyDetail() {
  return (
    <div className="rounded-2xl border border-dashed border-[#E8D4CB] bg-[#FFF8F4] p-8 text-sm text-[#7A625A]">
      选择一条记录查看详情。
    </div>
  );
}

function getRecordTone(recordType: string) {
  return (
    recordTypeTone[recordType] ?? {
      label: recordType,
      accent: "bg-[#B47767]",
      surface: "border-[#E8D4CB] bg-[#FFF8F4]",
      text: "text-[#9E5C4D]",
    }
  );
}

function getRecordHeadline(record: RawRecord): string {
  const content = asRecord(record.content);
  const payload = asRecord(content.payload);
  return (
    getString(content.headline) ||
    getString(content.title) ||
    getString(content.full_name) ||
    getString(payload.name) ||
    record.recordType
  );
}

function getSourceLabel(record: RawRecord): string {
  if (record.sourceUrl) {
    return record.sourceUrl;
  }
  const content = asRecord(record.content);
  const payload = asRecord(content.payload);
  return getString(content.full_name) || getString(payload.name) || "手动录入事实";
}

function getContentSize(content: RawRecord["content"]): number {
  return JSON.stringify(content).length;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function getString(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
