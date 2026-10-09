"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Database,
  RefreshCw,
  Loader2,
  Package,
  Eye,
  Search,
  X,
  Download,
  CheckSquare,
  Square,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { PlatformLogo } from "@/components/platforms/platform-logo";
import { DataPreviewDrawer } from "@/components/datasets/data-preview-drawer";
import {
  CATEGORIES,
  PLATFORM_LABELS,
  datasetCategory,
  getPlatformLabel,
  type CategoryKey,
} from "@/lib/platforms/catalog";
import {
  exportAndDownload,
  fetchDatasets,
  type DatasetListItem,
} from "@/lib/api/datasets";

/* Dataset types imply a coarse platform when the originating endpoint cannot
   be resolved server-side (e.g. records saved from a workflow). */
const DATASET_TYPE_PLATFORM: Record<string, string> = {
  ecommerce_product: "ecommerce",
  public_content_update: "web",
  github_tool_radar: "github",
};

/**
 * Frontend fallback for platform attribution: the backend derives real
 * platforms from the originating endpoint, but falls back to keyword matching
 * against the dataset name/description when that lineage is missing.
 */
function inferPlatforms(item: DatasetListItem): string[] {
  if (item.platforms.length > 0) return item.platforms;
  const hay = `${item.dataset.name} ${item.dataset.description ?? ""}`.toLowerCase();
  const hits = Object.keys(PLATFORM_LABELS).filter(
    k => k.length > 1 && hay.includes(k),
  );
  const inferred = Array.from(new Set(hits)).slice(0, 3);
  if (inferred.length > 0) return inferred;
  const byType = DATASET_TYPE_PLATFORM[item.dataset.dataset_type];
  return byType ? [byType] : [];
}

type TimeRange = "all" | "today" | "7d" | "30d";
type SortKey = "updated" | "rows" | "name";

/* Captured once at module load so render stays pure (Date.now() is impure). */
const PAGE_LOAD_TS = Date.now();
const DAY_MS = 86_400_000;
const WEEK_MS = 7 * DAY_MS;

const TIME_RANGES: { key: TimeRange; label: string }[] = [
  { key: "all", label: "全部时段" },
  { key: "today", label: "今日更新" },
  { key: "7d", label: "近 7 天" },
  { key: "30d", label: "近 30 天" },
];

const SORTS: { key: SortKey; label: string }[] = [
  { key: "updated", label: "按更新时间" },
  { key: "rows", label: "按记录数" },
  { key: "name", label: "按名称" },
];

function withinRange(iso: string, range: TimeRange): boolean {
  if (range === "all") return true;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return false;
  if (range === "today") {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    return t >= start.getTime();
  }
  if (range === "7d") return t >= PAGE_LOAD_TS - WEEK_MS;
  return t >= PAGE_LOAD_TS - 30 * DAY_MS;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
}

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-5 py-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-[var(--text-primary)]">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">{hint}</p> : null}
    </div>
  );
}

export default function DatasetsPage() {
  const [category, setCategory] = useState<CategoryKey>("all");
  const [platformFilter, setPlatformFilter] = useState<string[]>([]);
  const [timeRange, setTimeRange] = useState<TimeRange>("all");
  const [sort, setSort] = useState<SortKey>("updated");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [drawerItem, setDrawerItem] = useState<DatasetListItem | null>(null);
  const [batch, setBatch] = useState<{ running: boolean; message: string | null }>({
    running: false,
    message: null,
  });

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["datasets"],
    queryFn: () => fetchDatasets({ limit: 100 }),
  });

  const items = useMemo(() => data?.items ?? [], [data]);

  // Attach the resolved platform list once so filters/stats share one source.
  const enriched = useMemo(
    () => items.map(item => ({ item, platforms: inferPlatforms(item) })),
    [items],
  );

  const categoryCounts = useMemo(() => {
    const counts = new Map<CategoryKey, number>();
    for (const { item, platforms } of enriched) {
      const key = datasetCategory(platforms, item.dataset.dataset_type);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  }, [enriched]);

  const platformOptions = useMemo(() => {
    const counts = new Map<string, number>();
    for (const { platforms } of enriched) {
      for (const p of platforms) counts.set(p, (counts.get(p) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([key, count]) => ({ key, count }));
  }, [enriched]);

  const stats = useMemo(() => {
    const totalRows = enriched.reduce(
      (sum, { item }) => sum + (item.latest_version?.row_count ?? 0),
      0,
    );
    const platforms = new Set(enriched.flatMap(({ platforms }) => platforms));
    const weekAgo = PAGE_LOAD_TS - WEEK_MS;
    const newThisWeek = enriched.filter(
      ({ item }) => new Date(item.dataset.created_at).getTime() >= weekAgo,
    ).length;
    return { datasets: enriched.length, totalRows, platforms: platforms.size, newThisWeek };
  }, [enriched]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = enriched.filter(({ item, platforms }) => {
      if (category !== "all" && datasetCategory(platforms, item.dataset.dataset_type) !== category) {
        return false;
      }
      if (platformFilter.length > 0 && !platformFilter.some(p => platforms.includes(p))) {
        return false;
      }
      if (!withinRange(item.dataset.updated_at, timeRange)) return false;
      if (q) {
        const hay = `${item.dataset.name} ${item.dataset.description ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    return filtered.sort((a, b) => {
      if (sort === "rows") {
        return (b.item.latest_version?.row_count ?? 0) - (a.item.latest_version?.row_count ?? 0);
      }
      if (sort === "name") {
        return a.item.dataset.name.localeCompare(b.item.dataset.name, "zh-CN");
      }
      return (
        new Date(b.item.dataset.updated_at).getTime() -
        new Date(a.item.dataset.updated_at).getTime()
      );
    });
  }, [enriched, category, platformFilter, timeRange, search, sort]);

  function toggleSelected(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function runBatchExport() {
    const targets = visible.filter(({ item }) => selected.has(item.dataset.id));
    if (targets.length === 0) return;
    setBatch({ running: true, message: `正在导出 ${targets.length} 个数据集…` });
    let done = 0;
    for (const { item } of targets) {
      if (!item.latest_version) continue;
      try {
        await exportAndDownload(item.dataset.id, item.latest_version.id, "csv");
        done += 1;
      } catch (err) {
        setBatch({
          running: false,
          message: `导出「${item.dataset.name}」失败：${err instanceof Error ? err.message : "未知错误"}`,
        });
        return;
      }
    }
    setBatch({ running: false, message: `已完成 ${done} 个数据集的导出` });
  }

  const allVisibleSelected =
    visible.length > 0 && visible.every(({ item }) => selected.has(item.dataset.id));

  return (
    <AppShell title="数据集" description="按平台、分类与时间切片预览和导出所有采集数据资产">
      {/* Stats HUD */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile label="数据集" value={stats.datasets.toLocaleString()} />
        <StatTile label="记录总量" value={stats.totalRows.toLocaleString()} />
        <StatTile label="覆盖平台" value={stats.platforms.toLocaleString()} />
        <StatTile label="本周新增" value={stats.newThisWeek.toLocaleString()} />
      </div>

      {/* Category tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {CATEGORIES.map(c => {
          const count = c.key === "all" ? enriched.length : categoryCounts.get(c.key) ?? 0;
          const active = category === c.key;
          return (
            <button
              key={c.key}
              type="button"
              onClick={() => setCategory(c.key)}
              className={`flex items-center gap-1.5 rounded-[var(--radius-pill)] border px-3 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                  : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]"
              }`}
            >
              {c.label}
              <span
                className={`rounded px-1.5 py-px text-[10px] font-bold tabular-nums ${
                  active
                    ? "bg-[var(--surface-primary)] text-[var(--action-primary)]"
                    : "bg-[var(--surface-muted)] text-[var(--text-tertiary)]"
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search
            size={14}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]"
          />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索数据集名称或描述"
            className="h-9 w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] pl-8 pr-8 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
          />
          {search ? (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label="清除搜索"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
            >
              <X size={13} />
            </button>
          ) : null}
        </div>
        <select
          value={timeRange}
          onChange={e => setTimeRange(e.target.value as TimeRange)}
          aria-label="时间范围"
          className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 text-xs text-[var(--text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
        >
          {TIME_RANGES.map(r => (
            <option key={r.key} value={r.key}>{r.label}</option>
          ))}
        </select>
        <select
          value={sort}
          onChange={e => setSort(e.target.value as SortKey)}
          aria-label="排序"
          className="h-9 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-2 text-xs text-[var(--text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
        >
          {SORTS.map(s => (
            <option key={s.key} value={s.key}>{s.label}</option>
          ))}
        </select>
        <button
          type="button"
          disabled={selected.size === 0 || batch.running}
          onClick={runBatchExport}
          className="flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-3 py-2 text-xs font-medium text-[var(--text-inverse)] transition-colors hover:bg-[var(--action-primary-hover)] disabled:opacity-50"
        >
          {batch.running ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
          批量导出{selected.size > 0 ? `（${selected.size}）` : ""}
        </button>
        <button
          type="button"
          onClick={() => refetch()}
          className="flex items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
        >
          <RefreshCw size={12} />
          刷新
        </button>
      </div>

      {/* Platform filter */}
      {platformOptions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-[var(--text-tertiary)]">平台</span>
          {platformOptions.map(({ key, count }) => {
            const active = platformFilter.includes(key);
            return (
              <button
                key={key}
                type="button"
                onClick={() =>
                  setPlatformFilter(prev =>
                    prev.includes(key) ? prev.filter(p => p !== key) : [...prev, key],
                  )
                }
                className={`flex items-center gap-1.5 rounded-[var(--radius-pill)] border px-2 py-1 text-xs transition-colors ${
                  active
                    ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                    : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]"
                }`}
              >
                <PlatformLogo platform={key} size={16} />
                {getPlatformLabel(key)}
                <span className="tabular-nums text-[var(--text-tertiary)]">{count}</span>
              </button>
            );
          })}
          {platformFilter.length > 0 ? (
            <button
              type="button"
              onClick={() => setPlatformFilter([])}
              className="text-xs text-[var(--text-tertiary)] underline hover:text-[var(--text-primary)]"
            >
              清除
            </button>
          ) : null}
        </div>
      ) : null}

      {batch.message ? (
        <p className="text-xs text-[var(--text-secondary)]">{batch.message}</p>
      ) : null}

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={24} className="animate-spin text-[var(--text-tertiary)]" />
        </div>
      ) : error ? (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--danger-soft)] p-6 text-sm text-[var(--state-danger)]">
          加载失败：{(error as Error).message}
        </div>
      ) : visible.length === 0 ? (
        <div className="rounded-[var(--radius-3)] border-2 border-dashed border-[var(--border-subtle)] py-16 text-center">
          <Package size={36} className="mx-auto text-[var(--text-tertiary)]" />
          <p className="mt-3 text-base font-semibold text-[var(--text-primary)]">
            {enriched.length === 0 ? "暂无数据集" : "没有符合筛选条件的数据集"}
          </p>
          <p className="mt-1 text-sm text-[var(--text-tertiary)]">
            {enriched.length === 0 ? "在「平台能力中心」完成采集并保存后，数据集会出现在这里" : "试试放宽平台或时间筛选"}
          </p>
        </div>
      ) : (
        <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--border-subtle)]">
                  <th className="w-10 px-4 py-3">
                    <button
                      type="button"
                      aria-label="全选"
                      onClick={() =>
                        setSelected(
                          allVisibleSelected
                            ? new Set()
                            : new Set(visible.map(({ item }) => item.dataset.id)),
                        )
                      }
                      className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                    >
                      {allVisibleSelected ? <CheckSquare size={14} /> : <Square size={14} />}
                    </button>
                  </th>
                  {["平台", "数据集", "版本与记录数", "完整度", "最近更新", "操作"].map(h => (
                    <th
                      key={h}
                      className="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map(({ item, platforms }) => {
                  const ds = item.dataset;
                  const version = item.latest_version;
                  const checked = selected.has(ds.id);
                  return (
                    <tr
                      key={ds.id}
                      className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--surface-muted)]"
                    >
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          aria-label={`选择 ${ds.name}`}
                          onClick={() => toggleSelected(ds.id)}
                          className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                        >
                          {checked ? <CheckSquare size={14} /> : <Square size={14} />}
                        </button>
                      </td>
                      <td className="px-4 py-3">
                        {platforms.length > 0 ? (
                          <div className="flex items-center gap-1">
                            {platforms.slice(0, 3).map(p => (
                              <PlatformLogo key={p} platform={p} size={22} />
                            ))}
                          </div>
                        ) : (
                          <PlatformLogo platform="web" size={22} />
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-start gap-2.5">
                          <Database size={15} className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-[var(--text-primary)]">{ds.name}</p>
                            <p className="mt-0.5 line-clamp-1 max-w-[420px] text-xs text-[var(--text-tertiary)]">
                              {ds.description ?? ds.dataset_type}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm text-[var(--text-secondary)]">
                          {version ? `v${version.version_number}` : "—"}
                        </span>
                        <span className="ml-2 tabular-nums text-xs text-[var(--text-tertiary)]">
                          {version ? `${version.row_count.toLocaleString()} 条` : ""}
                          {item.version_count > 1 ? ` · ${item.version_count} 版` : ""}
                        </span>
                      </td>
                      <td className="px-4 py-3 tabular-nums text-sm text-[var(--text-secondary)]">
                        {version ? `${version.average_completeness_percent}%` : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-[var(--text-tertiary)]">
                        {formatDate(ds.updated_at)}
                      </td>
                      <td className="px-4 py-3">
                        {version ? (
                          <button
                            type="button"
                            onClick={() => setDrawerItem(item)}
                            className="flex items-center gap-1 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors hover:bg-[var(--accent-1-soft)] hover:text-[var(--action-primary)]"
                          >
                            <Eye size={12} />
                            预览
                          </button>
                        ) : (
                          <span className="text-xs text-[var(--text-tertiary)]">无版本</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <DataPreviewDrawer
        key={drawerItem?.dataset.id ?? "none"}
        open={drawerItem !== null}
        onClose={() => setDrawerItem(null)}
        datasetId={drawerItem?.dataset.id ?? ""}
        datasetName={drawerItem?.dataset.name ?? ""}
        platforms={drawerItem ? inferPlatforms(drawerItem) : []}
        initialVersion={drawerItem?.latest_version ?? null}
      />
    </AppShell>
  );
}
