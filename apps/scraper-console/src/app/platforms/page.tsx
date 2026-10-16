"use client";

import { useState, useMemo, useRef, useCallback, useEffect, Suspense } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
  Search, X, ChevronDown, ChevronRight,
  CheckSquare, Square, Play,
  LayoutGrid, Globe, Package,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { QuickCollectDrawer } from "@/components/platforms/quick-collect-drawer";
import { fetchCollectorCatalog } from "@/lib/api/collectors";
import type { CollectorEndpoint } from "@/lib/api/collectors";
import { canStartCollection } from "@/lib/collection-policy";
import { fetchProviderStatus } from "@/lib/api/platform-packages";
import {
  BlockerList,
  ReachabilityBadge,
  ReachabilityProvider,
  useAvailability,
  type AvailabilityLookup,
} from "@/components/ui/reachability-badge";
import { resolveReachability } from "@/lib/reachability";
import { endpointRowKey } from "@/lib/endpoint-key";
import {
  mergeParams,
  hrefWithParams,
  SEARCH_DEBOUNCE_MS,
  type ParamUpdates,
} from "@/lib/url-state";
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
  const availability = useAvailability(endpoint.endpoint_type);
  const isVerified = canStartCollection(endpoint);

  // 可达性输入。结构性字段优先，策略原因兜底。
  const reachabilityInput = {
    catalogStatus: endpoint.status,
    policyBlockReason: endpoint.policy_block_reason ?? availability?.policy_block_reason ?? null,
    missingConfiguration: availability?.missing_configuration ?? [],
    availability: availability?.availability ?? null,
  };
  const reachability = resolveReachability(reachabilityInput);

  // 永久不可达与已停用不留操作入口。
  const canAct = isVerified && reachability.canRun;

  function handleClick() {
    if (!canAct) return;
    if (batchMode) onToggleSelect(endpoint);
    else onCollect(endpoint);
  }

  return (
    <div
      role="button"
      tabIndex={canAct ? 0 : -1}
      onClick={handleClick}
      onKeyDown={e => e.key === "Enter" && handleClick()}
      className={[
        "group flex items-start gap-3 rounded-lg border px-4 py-3 transition-all duration-100",
        canAct
          ? selected
            ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] cursor-pointer"
            : "border-[var(--border-subtle)] bg-[var(--surface-primary)] cursor-pointer hover:border-[var(--border-strong)] hover:bg-[var(--surface-muted)]"
          : "border-[var(--border-subtle)] bg-[var(--surface-primary)] opacity-40 cursor-default",
      ].join(" ")}
    >
      {/* batch checkbox */}
      {batchMode && canAct && (
        <span className="mt-0.5 flex-shrink-0 text-[var(--text-tertiary)]">
          {selected
            ? <CheckSquare size={14} className="text-[var(--action-primary)]" />
            : <Square size={14} />}
        </span>
      )}

      {/* status dot + 可达性徽标 */}
      <span className="mt-1.5 flex flex-shrink-0 items-center gap-1.5">
        <StatusDot status={endpoint.policy_block_reason ? "disabled" : endpoint.status} />
        <ReachabilityBadge input={reachabilityInput} />
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
        {reachability.blockers.length > 0 && (
          <BlockerList reachability={reachability} />
        )}
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
        {canAct && !batchMode && (
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
            key={endpointRowKey(ep)}
            endpoint={ep}
            onCollect={onCollect}
            batchMode={batchMode}
            selected={selectedEndpoints.has(endpointRowKey(ep))}
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

function PlatformsPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // 批量流程的当前端点。不进 URL。
  const [batchEndpoint, setBatchEndpoint] = useState<CollectorEndpoint | null>(null);
  const [batchMode, setBatchMode] = useState(false);
  const [selectedEndpoints, setSelectedEndpoints] = useState<Set<string>>(new Set());
  const [batchQueue, setBatchQueue] = useState<CollectorEndpoint[]>([]);
  const [batchQueueIndex, setBatchQueueIndex] = useState(0);
  // 本次打开是否压入过历史。关闭时据此决定 Back 还是清除参数。
  const [openedViaPush, setOpenedViaPush] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 分类与搜索词存在 URL。便于分享与返回。
  const categoryParam = searchParams.get("cat");
  const category: CategoryKey =
    categoryParam && CATEGORIES.some(c => c.key === categoryParam)
      ? (categoryParam as CategoryKey)
      : "all";
  const search = searchParams.get("q") ?? "";

  // 搜索框草稿。只在它基于的 URL 值仍是当前值时才生效。
  // 这样浏览器返回与前进时以 URL 为准。
  const [searchDraft, setSearchDraft] = useState<{ base: string; value: string } | null>(null);
  const searchValue = searchDraft && searchDraft.base === search ? searchDraft.value : search;

  // 写入 URL。替换当前记录，避免每次按键留一条历史。
  function applyParams(updates: ParamUpdates) {
    const query = mergeParams(new URLSearchParams(searchParams.toString()), updates);
    router.replace(hrefWithParams(pathname, query), { scroll: false });
  }

  // 卸载时清掉待写入的搜索词。
  useEffect(() => () => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ["collector-catalog"],
    queryFn: fetchCollectorCatalog,
  });

  const allEndpoints = useMemo(() => {
    if (!data) return [];
    return data.collectors.flatMap(c => c.endpoints).filter(e => e.status !== "disabled");
  }, [data]);

  // 实时可用性。三态标记的唯一来源。
  const providerStatus = useQuery({
    queryKey: ["provider-status"],
    queryFn: fetchProviderStatus,
  });
  const availabilityLookup: AvailabilityLookup = useMemo(() => {
    const map = new Map(
      (providerStatus.data?.endpoints ?? []).map(e => [e.endpoint_type, e])
    );
    return (endpointType: string) => map.get(endpointType) ?? null;
  }, [providerStatus.data]);

  // URL 深链：由 ep + label 定位一行。
  // label 单用会撞名，endpoint_type 单用会撞到同类型的 23 行。
  const epParam = searchParams.get("ep");
  const labelParam = searchParams.get("label");
  const deepLinkKey = epParam && labelParam ? `${epParam}:${labelParam}` : null;

  // URL 深链的抽屉目标。纯派生，不需要同步 effect。
  const deepLinkEndpoint = useMemo(() => {
    if (!deepLinkKey) return null;
    return allEndpoints.find(e => endpointRowKey(e) === deepLinkKey) ?? null;
  }, [deepLinkKey, allEndpoints]);

  // 抽屉目标。批量流程优先。
  const activeEndpoint = batchEndpoint ?? deepLinkEndpoint;

  // 打开抽屉。写入 URL，使链接可分享、Back 可关闭。
  function openEndpoint(ep: CollectorEndpoint) {
    setOpenedViaPush(true);
    const query = mergeParams(new URLSearchParams(searchParams.toString()), {
      ep: ep.endpoint_type,
      label: ep.label,
    });
    router.push(hrefWithParams(pathname, query), { scroll: false });
  }

  // 关闭抽屉。压过历史就回退一步，否则清掉 URL 参数。
  function closeEndpoint() {
    if (openedViaPush) {
      setOpenedViaPush(false);
      router.back();
      return;
    }
    applyParams({ ep: null, label: null });
  }

  const stats = useMemo(() => ({
    total:     allEndpoints.filter(canStartCollection).length,
    platforms: new Set(allEndpoints.map(e => e.platform)).size,
    types:     new Set(allEndpoints.map(e => e.content_type)).size,
  }), [allEndpoints]);

  // Category counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const cat of CATEGORIES) {
      counts[cat.key] = cat.key === "all"
        ? allEndpoints.filter(canStartCollection).length
        : allEndpoints.filter(e =>
            canStartCollection(e) && matchCategory(e.platform, cat.filterKeys)
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
  // 选择集以行标识为键。同一 endpoint_type 的多行互不影响。
  const toggleSelect = useCallback((ep: CollectorEndpoint) => {
    setSelectedEndpoints(prev => {
      const n = new Set(prev);
      const key = endpointRowKey(ep);
      if (n.has(key)) n.delete(key);
      else n.add(key);
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
    // 行标识已唯一。队列保留用户实际勾选的行。
    const queue = allEndpoints.filter(
      ep => selectedEndpoints.has(endpointRowKey(ep)) && canStartCollection(ep)
    );
    if (!queue.length) return;
    setBatchQueue(queue);
    setBatchQueueIndex(0);
    setOpenedViaPush(false);
    setBatchEndpoint(queue[0]);
  }

  function onBatchAbort() {
    setBatchQueue([]);
    setBatchQueueIndex(0);
    setSelectedEndpoints(new Set());
    setOpenedViaPush(false);
    setBatchEndpoint(null);
  }

  function onBatchDrawerClose() {
    setOpenedViaPush(false);
    const next = batchQueueIndex + 1;
    if (next < batchQueue.length) {
      setBatchQueueIndex(next);
      setBatchEndpoint(batchQueue[next]);
    } else {
      setBatchQueue([]);
      setBatchQueueIndex(0);
      setBatchEndpoint(null);
    }
  }

  return (
    <AppShell
      title="平台能力中心"
      description={`${stats.total} 种可执行采集能力 · ${stats.platforms} 个平台 · ${stats.types} 种数据类型`}
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
              { label: "可执行采集能力", value: stats.total,     unit: "个" },
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
                    onClick={() => applyParams({ cat: cat.key === "all" ? null : cat.key })}
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
                  value={searchValue}
                  onChange={e => {
                    const next = e.target.value;
                    setSearchDraft({ base: search, value: next });
                    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
                    searchTimerRef.current = setTimeout(() => {
                      applyParams({ q: next.trim() || null });
                    }, SEARCH_DEBOUNCE_MS);
                  }}
                  placeholder="搜索平台、采集能力…"
                  className="h-9 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] pl-8 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
                />
                {search && (
                  <button
                    onClick={() => {
                      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
                      setSearchDraft(null);
                      applyParams({ q: null });
                    }}
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
                onClick={() => {
                  if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
                  setSearchDraft(null);
                  applyParams({ q: null, cat: null });
                }}
                className="mt-2 text-xs text-[var(--action-primary)] underline"
              >
                清空筛选
              </button>
            </div>
          ) : (
            <ReachabilityProvider lookup={availabilityLookup}>
            <div className="flex flex-col gap-6">
              {byPlatform.map(({ platform, endpoints }) => (
                <PlatformSection
                  key={platform}
                  platform={platform}
                  endpoints={endpoints}
                  onCollect={openEndpoint}
                  batchMode={batchMode}
                  selectedEndpoints={selectedEndpoints}
                  onToggleSelect={toggleSelect}
                />
              ))}
            </div>
            </ReachabilityProvider>
          )}
        </div>
      )}

      {activeEndpoint && (
        <QuickCollectDrawer
          key={`${activeEndpoint.endpoint_type}:${activeEndpoint.label}`}
          endpoint={activeEndpoint}
          open={!!activeEndpoint}
          onClose={batchQueue.length > 0 ? onBatchDrawerClose : closeEndpoint}
          onAbort={batchQueue.length > 0 ? onBatchAbort : undefined}
          batchProgress={
            batchQueue.length > 0
              ? { index: batchQueueIndex, total: batchQueue.length }
              : null
          }
        />
      )}
    </AppShell>
  );
}

export default function PlatformsPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="平台能力中心" description="">
          <div className="flex items-center justify-center py-24">
            <span className="text-sm text-[var(--text-tertiary)]">加载采集能力目录…</span>
          </div>
        </AppShell>
      }
    >
      <PlatformsPageContent />
    </Suspense>
  );
}
