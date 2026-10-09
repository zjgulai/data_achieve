"use client";

import { useState, useMemo, useRef, useCallback } from "react";
import {
  Search, X, ChevronDown, ChevronRight,
  CheckSquare, Square, Play,
  LayoutGrid, Globe, Package,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { QuickCollectDrawer } from "@/components/platforms/quick-collect-drawer";
import { fetchCollectorCatalog } from "@/lib/api/collectors";
import type { CollectorEndpoint } from "@/lib/api/collectors";
import { useQuery } from "@tanstack/react-query";
import { PlatformLogo } from "@/components/platforms/platform-logo";
import {
  CATEGORIES,
  CONTENT_TYPE_LABELS,
  CONTENT_TYPE_ORDER,
  METHOD_LABELS,
  PLATFORM_LABELS,
  getPlatformLabel,
  matchCategory,
  type CategoryKey,
} from "@/lib/platforms/catalog";


function StatusDot({ status }: { status: string }) {
  const color =
    status === "verified" ? "var(--state-success)"
    : status === "pending" ? "var(--state-warning)"
    : "var(--border-strong)";
  return (
    <span
      style={{
        display: "inline-block",
        width: 6,
        height: 6,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
      }}
    />
  );
}

/* ─────────────────────────────────────────────────────────────
   EndpointRow — compact list item inside a method section
───────────────────────────────────────────────────────────── */

function EndpointRow({
  endpoint,
  onCollect,
  batchMode,
  selected,
  onToggleSelect,
}: {
  endpoint: CollectorEndpoint;
  onCollect: (ep: CollectorEndpoint) => void;
  batchMode: boolean;
  selected: boolean;
  onToggleSelect: (ep: CollectorEndpoint) => void;
}) {
  const isVerified = endpoint.status === "verified";

  function handleClick() {
    if (!isVerified) return;
    if (batchMode) onToggleSelect(endpoint);
    else onCollect(endpoint);
  }

  return (
    <div
      role="button"
      tabIndex={isVerified ? 0 : -1}
      onClick={handleClick}
      onKeyDown={e => e.key === "Enter" && handleClick()}
      className={[
        "group flex items-start gap-3 rounded-lg border px-4 py-3 transition-all duration-100",
        isVerified
          ? selected
            ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] cursor-pointer"
            : "border-[var(--border-subtle)] bg-[var(--surface-primary)] cursor-pointer hover:border-[var(--border-strong)] hover:bg-[var(--surface-muted)]"
          : "border-[var(--border-subtle)] bg-[var(--surface-primary)] opacity-40 cursor-default",
      ].join(" ")}
    >
      {/* batch checkbox */}
      {batchMode && isVerified && (
        <span className="mt-0.5 flex-shrink-0 text-[var(--text-tertiary)]">
          {selected
            ? <CheckSquare size={14} className="text-[var(--action-primary)]" />
            : <Square size={14} />}
        </span>
      )}

      {/* status dot */}
      <span className="mt-1.5 flex-shrink-0">
        <StatusDot status={endpoint.status} />
      </span>

      {/* label + description */}
      <div className="min-w-0 flex-1">
        <p className={[
          "text-sm font-medium leading-snug",
          selected
            ? "text-[var(--action-primary)]"
            : "text-[var(--text-primary)] group-hover:text-[var(--action-primary)]",
        ].join(" ")}>
          {endpoint.label}
        </p>
        <p className="mt-0.5 text-xs leading-relaxed text-[var(--text-tertiary)] line-clamp-2">
          {endpoint.description}
        </p>
        {endpoint.required_params.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {endpoint.required_params.slice(0, 4).map(p => (
              <span
                key={p}
                className="rounded border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-1.5 py-px text-[10px] text-[var(--text-tertiary)] font-mono"
              >
                {p}
              </span>
            ))}
            {endpoint.required_params.length > 4 && (
              <span className="text-[10px] text-[var(--text-tertiary)]">
                +{endpoint.required_params.length - 4}
              </span>
            )}
          </div>
        )}
      </div>

      {/* cost hint + chevron */}
      <div className="flex flex-shrink-0 flex-col items-end gap-1">
        {endpoint.cost_hint && (
          <span className="text-[10px] text-[var(--text-tertiary)]">{endpoint.cost_hint}</span>
        )}
        {isVerified && !batchMode && (
          <ChevronRight
            size={14}
            className="text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity"
          />
        )}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   MethodSection — one method (TikHub / Apify / …) inside a content-type panel
───────────────────────────────────────────────────────────── */

function MethodSection({
  method,
  endpoints,
  onCollect,
  batchMode,
  selectedEndpoints,
  onToggleSelect,
}: {
  method: string;
  endpoints: CollectorEndpoint[];
  onCollect: (ep: CollectorEndpoint) => void;
  batchMode: boolean;
  selectedEndpoints: Set<string>;
  onToggleSelect: (ep: CollectorEndpoint) => void;
}) {
  const label = METHOD_LABELS[method] ?? method;
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
          {label}
        </span>
        <span className="text-[11px] tabular-nums text-[var(--text-tertiary)]">
          {endpoints.length}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {endpoints.map(ep => (
          <EndpointRow
            key={ep.endpoint_type}
            endpoint={ep}
            onCollect={onCollect}
            batchMode={batchMode}
            selected={selectedEndpoints.has(ep.endpoint_type)}
            onToggleSelect={onToggleSelect}
          />
        ))}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   ContentTypePanel — collapsible panel for one content type
   (e.g. "内容帖子") with method sections inside
───────────────────────────────────────────────────────────── */

function ContentTypePanel({
  contentType,
  endpoints,
  onCollect,
  batchMode,
  selectedEndpoints,
  onToggleSelect,
  defaultOpen,
}: {
  contentType: string;
  endpoints: CollectorEndpoint[];
  onCollect: (ep: CollectorEndpoint) => void;
  batchMode: boolean;
  selectedEndpoints: Set<string>;
  onToggleSelect: (ep: CollectorEndpoint) => void;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  // group by method, preserve a stable order
  const METHOD_ORDER = [
    "tikhub", "apify", "github_api", "anysearch", "exa",
    "jina_reader", "rss", "web_crawl", "browser",
  ];
  const byMethod = useMemo(() => {
    const map: Record<string, CollectorEndpoint[]> = {};
    for (const ep of endpoints) (map[ep.method] ??= []).push(ep);
    const sorted = METHOD_ORDER.filter(k => map[k]);
    const rest = Object.keys(map).filter(k => !METHOD_ORDER.includes(k));
    return [...sorted, ...rest].map(m => ({ method: m, endpoints: map[m] }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endpoints]);

  const label = CONTENT_TYPE_LABELS[contentType] ?? contentType;

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] overflow-hidden">
      {/* header */}
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center justify-between px-5 py-3.5 hover:bg-[var(--surface-muted)] transition-colors text-left"
      >
        <div className="flex items-center gap-2.5">
          <span className="text-sm font-semibold text-[var(--text-primary)]">{label}</span>
          <span className="rounded border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-2 py-px text-[11px] tabular-nums text-[var(--text-tertiary)]">
            {endpoints.length}
          </span>
        </div>
        {open
          ? <ChevronDown size={15} className="text-[var(--text-tertiary)]" />
          : <ChevronRight size={15} className="text-[var(--text-tertiary)]" />}
      </button>

      {/* body */}
      {open && (
        <div className="border-t border-[var(--border-subtle)] px-5 pb-5 pt-4">
          <div className="flex flex-col gap-6">
            {byMethod.map(({ method, endpoints: eps }) => (
              <MethodSection
                key={method}
                method={method}
                endpoints={eps}
                onCollect={onCollect}
                batchMode={batchMode}
                selectedEndpoints={selectedEndpoints}
                onToggleSelect={onToggleSelect}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   PlatformSection — one platform block with logo header +
   content-type tab bar + content panels
───────────────────────────────────────────────────────────── */

function PlatformSection({
  platform,
  endpoints,
  onCollect,
  batchMode,
  selectedEndpoints,
  onToggleSelect,
}: {
  platform: string;
  endpoints: CollectorEndpoint[];
  onCollect: (ep: CollectorEndpoint) => void;
  batchMode: boolean;
  selectedEndpoints: Set<string>;
  onToggleSelect: (ep: CollectorEndpoint) => void;
}) {
  const contentTypes = useMemo(() => {
    const seen = new Set<string>();
    const result: string[] = [];
    for (const ct of CONTENT_TYPE_ORDER) {
      if (endpoints.some(e => e.content_type === ct)) { seen.add(ct); result.push(ct); }
    }
    for (const ep of endpoints) {
      if (!seen.has(ep.content_type)) { seen.add(ep.content_type); result.push(ep.content_type); }
    }
    return result;
  }, [endpoints]);

  const [activeType, setActiveType] = useState<string | null>(null);
  const shownType = activeType ?? contentTypes[0] ?? null;

  const shownEndpoints = useMemo(
    () => (shownType ? endpoints.filter(e => e.content_type === shownType) : []),
    [endpoints, shownType],
  );

  return (
    <div className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] overflow-hidden">
      {/* Platform header */}
      <div className="flex items-center gap-4 border-b border-[var(--border-subtle)] bg-[var(--surface-muted)] px-6 py-5">
        <PlatformLogo platform={platform} size={48} />
        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)] leading-tight">
            {getPlatformLabel(platform)}
          </h2>
          <p className="mt-0.5 text-xs text-[var(--text-tertiary)]">
            {endpoints.length} 种采集能力
          </p>
        </div>
      </div>

      {/* Content-type tabs (Level 2) */}
      <div className="flex items-center gap-0 overflow-x-auto border-b border-[var(--border-subtle)] px-6">
        {contentTypes.map(ct => {
          const label = CONTENT_TYPE_LABELS[ct] ?? ct;
          const count = endpoints.filter(e => e.content_type === ct).length;
          const isActive = ct === shownType;
          return (
            <button
              key={ct}
              onClick={() => setActiveType(ct)}
              className={[
                "flex-shrink-0 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px",
                isActive
                  ? "border-[var(--action-primary)] text-[var(--action-primary)]"
                  : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
              ].join(" ")}
            >
              {label}
              <span className={[
                "ml-1.5 text-[11px] tabular-nums",
                isActive ? "text-[var(--action-primary)]" : "text-[var(--text-tertiary)]",
              ].join(" ")}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Method sections (Level 3) */}
      {shownType && (
        <div className="px-6 py-5">
          <ContentTypePanel
            key={`${platform}-${shownType}`}
            contentType={shownType}
            endpoints={shownEndpoints}
            onCollect={onCollect}
            batchMode={batchMode}
            selectedEndpoints={selectedEndpoints}
            onToggleSelect={onToggleSelect}
            defaultOpen
          />
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Main page
───────────────────────────────────────────────────────────── */

export default function PlatformsPage() {
  const [activeEndpoint, setActiveEndpoint] = useState<CollectorEndpoint | null>(null);
  const [category, setCategory] = useState<CategoryKey>("all");
  const [search, setSearch] = useState("");
  const [batchMode, setBatchMode] = useState(false);
  const [selectedEndpoints, setSelectedEndpoints] = useState<Set<string>>(new Set());
  const [batchQueue, setBatchQueue] = useState<CollectorEndpoint[]>([]);
  const [batchQueueIndex, setBatchQueueIndex] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["collector-catalog"],
    queryFn: fetchCollectorCatalog,
  });

  const allEndpoints = useMemo(() => {
    if (!data) return [];
    return data.collectors.flatMap(c => c.endpoints).filter(e => e.status !== "disabled");
  }, [data]);

  const stats = useMemo(() => ({
    total:     allEndpoints.filter(e => e.status === "verified").length,
    platforms: new Set(allEndpoints.map(e => e.platform)).size,
    types:     new Set(allEndpoints.map(e => e.content_type)).size,
  }), [allEndpoints]);

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const cat of CATEGORIES) {
      counts[cat.key] = cat.key === "all"
        ? allEndpoints.filter(e => e.status === "verified").length
        : allEndpoints.filter(e =>
            e.status === "verified" && matchCategory(e.platform, cat.filterKeys)
          ).length;
    }
    return counts;
  }, [allEndpoints]);

  // Filter pipeline: category + search
  const filtered = useMemo(() => {
    const cat = CATEGORIES.find(c => c.key === category)!;
    let eps = cat.key === "all"
      ? allEndpoints
      : allEndpoints.filter(e => matchCategory(e.platform, cat.filterKeys));

    if (search.trim()) {
      const q = search.toLowerCase();
      eps = eps.filter(e =>
        e.label.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        e.platform.toLowerCase().includes(q) ||
        (PLATFORM_LABELS[e.platform]?.toLowerCase().includes(q) ?? false)
      );
    }
    return eps;
  }, [allEndpoints, category, search]);

  // Group by platform, preserving a sensible order
  const PLATFORM_ORDER: string[] = [
    "tiktok", "instagram", "youtube", "x", "facebook", "threads",
    "pinterest", "reddit", "lemon8", "snapchat", "bluesky", "telegram",
    "xiaohongshu", "linkedin",
    "douyin", "bilibili", "weibo", "kuaishou", "wechat", "zhihu",
    "amazon", "walmart", "temu", "shein", "aliexpress",
    "tiktok_shop", "ebay", "etsy", "shopify", "target", "ecommerce",
    "trustpilot", "appstore", "tripadvisor", "yelp",
    "booking", "airbnb", "glassdoor", "google_maps", "google_play",
    "google_search", "google_trends", "google_news", "chatgpt", "perplexity", "gemini",
    "facebook_ads", "google_ads", "tiktok_ads", "snapchat_ads", "pinterest_ads",
    "product_hunt", "crunchbase", "hacker_news", "indeed", "github",
    "regulatory", "rss", "web",
  ];

  const byPlatform = useMemo(() => {
    const map: Record<string, CollectorEndpoint[]> = {};
    for (const ep of filtered) (map[ep.platform] ??= []).push(ep);
    const inOrder = PLATFORM_ORDER.filter(p => map[p]);
    const rest = Object.keys(map).filter(p => !PLATFORM_ORDER.includes(p)).sort();
    return [...inOrder, ...rest].map(p => ({ platform: p, endpoints: map[p] }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered]);

  // Batch helpers
  const toggleSelect = useCallback((ep: CollectorEndpoint) => {
    setSelectedEndpoints(prev => {
      const n = new Set(prev);
      n.has(ep.endpoint_type) ? n.delete(ep.endpoint_type) : n.add(ep.endpoint_type);
      return n;
    });
  }, []);

  function toggleBatchMode() {
    setBatchMode(prev => !prev);
    setSelectedEndpoints(new Set());
    setBatchQueue([]);
    setBatchQueueIndex(0);
  }

  function startBatchCollect() {
    const queue = allEndpoints.filter(ep => selectedEndpoints.has(ep.endpoint_type));
    if (!queue.length) return;
    setBatchQueue(queue);
    setBatchQueueIndex(0);
    setActiveEndpoint(queue[0]);
  }

  function onBatchDrawerClose() {
    setActiveEndpoint(null);
    const next = batchQueueIndex + 1;
    if (next < batchQueue.length) {
      setBatchQueueIndex(next);
      setActiveEndpoint(batchQueue[next]);
    } else {
      setBatchQueue([]);
      setBatchQueueIndex(0);
    }
  }

  return (
    <AppShell
      title="平台能力中心"
      description={`${stats.total} 种已验证采集能力 · ${stats.platforms} 个平台 · ${stats.types} 种数据类型`}
      brief="选择平台和数据类型，然后选择采集方案启动"
    >
      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <span className="text-sm text-[var(--text-tertiary)]">加载采集能力目录…</span>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-[var(--state-danger)] bg-[var(--danger-soft)] p-10 text-center">
          <p className="text-sm font-medium text-[var(--state-danger)]">后端未连接，请先启动 API 服务</p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">{(error as Error).message}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "已验证采集能力", value: stats.total,     unit: "个" },
              { label: "覆盖平台",       value: stats.platforms, unit: "个" },
              { label: "数据类型",       value: stats.types,     unit: "种" },
            ].map(s => (
              <div
                key={s.label}
                className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-5 py-4"
              >
                <div className="flex items-baseline gap-1.5">
                  <span className="text-3xl font-bold tabular-nums text-[var(--text-primary)]">
                    {s.value}
                  </span>
                  <span className="text-xs text-[var(--text-tertiary)]">{s.unit}</span>
                </div>
                <div className="mt-1 text-xs text-[var(--text-tertiary)]">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Toolbar: category tabs + search + batch */}
          <div className="flex flex-col gap-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-5 py-4">
            {/* Category tabs */}
            <div className="flex flex-wrap gap-2">
              {CATEGORIES.map(cat => {
                const active = category === cat.key;
                const count = categoryCounts[cat.key] ?? 0;
                return (
                  <button
                    key={cat.key}
                    onClick={() => setCategory(cat.key)}
                    className={[
                      "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-all duration-100",
                      active
                        ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)] shadow-sm"
                        : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    {cat.key === "all" && (
                      <LayoutGrid size={13} className={active ? "text-[var(--text-inverse)]" : "text-[var(--text-tertiary)]"} />
                    )}
                    {cat.label}
                    <span className={[
                      "rounded px-1.5 py-px text-[10px] font-bold tabular-nums",
                      active
                        ? "bg-white/20 text-[var(--text-inverse)]"
                        : "bg-[var(--surface-muted)] text-[var(--text-tertiary)]",
                    ].join(" ")}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Search + batch */}
            <div className="flex items-center gap-3">
              <div className="relative flex-1 min-w-48">
                <Search
                  size={13}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]"
                />
                <input
                  ref={searchRef}
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="搜索平台、采集能力…"
                  className="h-9 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] pl-8 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
                />
                {search && (
                  <button
                    onClick={() => setSearch("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                  >
                    <X size={13} />
                  </button>
                )}
              </div>

              <button
                onClick={toggleBatchMode}
                className={[
                  "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors flex-shrink-0",
                  batchMode
                    ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                    : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]",
                ].join(" ")}
              >
                <CheckSquare size={14} />
                {batchMode ? "退出批量" : "批量采集"}
              </button>

              {batchMode && selectedEndpoints.size > 0 && (
                <>
                  <button
                    onClick={startBatchCollect}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--action-primary)] px-3 py-1.5 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] transition-colors"
                  >
                    <Play size={13} />
                    逐个启动 ({selectedEndpoints.size})
                  </button>
                  <button
                    onClick={() => setSelectedEndpoints(new Set())}
                    className="text-xs text-[var(--text-tertiary)] hover:text-[var(--state-danger)] transition-colors"
                  >
                    清空选择
                  </button>
                </>
              )}

              {/* result count */}
              <span className="ml-auto flex-shrink-0 text-xs tabular-nums text-[var(--text-tertiary)]">
                {filtered.length} 个能力
                {search && <span className="ml-1">(已搜索)</span>}
              </span>
            </div>
          </div>

          {/* Platform sections */}
          {byPlatform.length === 0 ? (
            <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] py-20 text-center">
              <p className="text-sm text-[var(--text-tertiary)]">没有匹配的采集能力</p>
              <button
                onClick={() => { setSearch(""); setCategory("all"); }}
                className="mt-2 text-xs text-[var(--action-primary)] underline"
              >
                清空筛选
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {byPlatform.map(({ platform, endpoints }) => (
                <PlatformSection
                  key={platform}
                  platform={platform}
                  endpoints={endpoints}
                  onCollect={setActiveEndpoint}
                  batchMode={batchMode}
                  selectedEndpoints={selectedEndpoints}
                  onToggleSelect={toggleSelect}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {activeEndpoint && (
        <QuickCollectDrawer
          endpoint={activeEndpoint}
          open={!!activeEndpoint}
          onClose={batchQueue.length > 0 ? onBatchDrawerClose : () => setActiveEndpoint(null)}
        />
      )}
    </AppShell>
  );
}
