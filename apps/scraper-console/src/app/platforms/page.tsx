"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, X, ChevronRight, Zap, Database, Globe, Rss, GitFork, CheckSquare, Square, Play } from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { QuickCollectDrawer } from "@/components/platforms/quick-collect-drawer";
import { fetchCollectorCatalog } from "@/lib/api/collectors";
import type { CollectorEndpoint } from "@/lib/api/collectors";

/* ─────────────────────────────────────────────
   常量：分类体系
───────────────────────────────────────────── */

const CONTENT_TYPE_META: Record<string, { label: string; emoji: string; desc: string }> = {
  post:      { label: "内容帖子",  emoji: "📝", desc: "视频、图文、推文等 UGC 内容" },
  comment:   { label: "用户评论",  emoji: "💬", desc: "帖子下的用户互动评论" },
  account:   { label: "账号档案",  emoji: "👤", desc: "品牌/KOL 账号主页信息" },
  product:   { label: "商品信息",  emoji: "🛒", desc: "电商平台商品详情与上架数据" },
  review:    { label: "用户评价",  emoji: "⭐", desc: "电商、地图、应用商店评价" },
  ad:        { label: "广告素材",  emoji: "📢", desc: "各平台在投广告创意与数据" },
  job:       { label: "招聘信息",  emoji: "💼", desc: "职位招聘与人才市场数据" },
  news:      { label: "新闻资讯",  emoji: "📰", desc: "媒体报道与行业新闻" },
  trend:     { label: "搜索趋势",  emoji: "📈", desc: "关键词热度与时间趋势" },
  ai_answer: { label: "AI 回答",   emoji: "🤖", desc: "ChatGPT / Perplexity / Gemini 搜索结果" },
  repo:      { label: "代码仓库",  emoji: "🗃️", desc: "GitHub 仓库与技术话题" },
  feed:      { label: "RSS 订阅",  emoji: "📡", desc: "标准 RSS / Atom 订阅源" },
  web_page:  { label: "网页快照",  emoji: "🌐", desc: "任意公开网页抓取与 RAG 解析" },
  search:    { label: "搜索结果",  emoji: "🔍", desc: "搜索引擎关键词结果页" },
};

const METHOD_META: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  tikhub:     { label: "TikHub API", color: "text-violet-700", bg: "bg-violet-50 border-violet-200",  icon: <Zap size={12} /> },
  apify:      { label: "Apify Actor", color: "text-sky-700",    bg: "bg-sky-50 border-sky-200",       icon: <Database size={12} /> },
  github_api: { label: "GitHub API",  color: "text-neutral-700", bg: "bg-neutral-50 border-neutral-200", icon: <GitFork size={12} /> },
  rss:        { label: "RSS 解析",    color: "text-orange-700",  bg: "bg-orange-50 border-orange-200", icon: <Rss size={12} /> },
  web_crawl:  { label: "通用爬取",   color: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200", icon: <Globe size={12} /> },
};

/* 平台分组：把所有 endpoint 的 platform 字段归并到大类 */
const PLATFORM_GROUP_META: Record<string, { label: string; emoji: string; platforms: string[] }> = {
  all:       { label: "全部",      emoji: "🌍", platforms: [] },
  social:    { label: "社交媒体", emoji: "📱", platforms: ["tiktok","instagram","xiaohongshu","youtube","x","facebook","threads","pinterest","bluesky","telegram","reddit"] },
  ecommerce: { label: "电商平台", emoji: "🛍️", platforms: ["amazon","walmart","temu","shein","aliexpress","tiktok_shop","ebay","etsy","shopify"] },
  review:    { label: "评价平台", emoji: "⭐", platforms: ["trustpilot","appstore","tripadvisor","yelp","booking","airbnb","glassdoor","google_maps"] },
  search:    { label: "搜索 & AI", emoji: "🔍", platforms: ["google","google_search","google_trends","google_news","google_maps","chatgpt","perplexity","gemini"] },
  ads:       { label: "广告情报", emoji: "📢", platforms: ["facebook_ads","google_ads","tiktok_ads","snapchat_ads","pinterest_ads"] },
  b2b:       { label: "B2B & 开源", emoji: "🏢", platforms: ["linkedin","glassdoor","product_hunt","crunchbase","hacker_news","indeed","github"] },
  open_web:  { label: "开放网络", emoji: "🌐", platforms: ["rss","web","public_feed","generic_web"] },
};

/* ─────────────────────────────────────────────
   工具函数
───────────────────────────────────────────── */

function getPlatformGroup(platform: string): string {
  for (const [key, meta] of Object.entries(PLATFORM_GROUP_META)) {
    if (key === "all") continue;
    if (meta.platforms.some(p => platform.toLowerCase().includes(p))) return key;
  }
  return "open_web";
}

/* ─────────────────────────────────────────────
   子组件
───────────────────────────────────────────── */

function StatusDot({ status }: { status: string }) {
  const cls = status === "verified" ? "bg-emerald-400" : status === "pending" ? "bg-amber-400" : "bg-red-400";
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${cls}`} />;
}

function MethodBadge({ method }: { method: string }) {
  const m = METHOD_META[method] ?? { label: method, color: "text-gray-600", bg: "bg-gray-50 border-gray-200", icon: null };
  return (
    <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${m.bg} ${m.color}`}>
      {m.icon}
      {m.label}
    </span>
  );
}

function ContentTypePill({ type }: { type: string }) {
  const meta = CONTENT_TYPE_META[type];
  if (!meta) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] text-[var(--text-tertiary)]">
      {meta.emoji} {meta.label}
    </span>
  );
}

/* 采集卡片 */
function EndpointCard({
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
    if (batchMode) {
      onToggleSelect(endpoint);
    } else {
      onCollect(endpoint);
    }
  }

  return (
    <div
      className={`group relative flex flex-col rounded-xl border bg-[var(--surface-primary)] p-4 transition-all duration-150
        ${isVerified
          ? selected
            ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] shadow-md cursor-pointer"
            : "border-[var(--border-subtle)] hover:border-[var(--action-primary)] hover:shadow-md cursor-pointer"
          : "border-[var(--border-subtle)] opacity-60"
        }`}
      onClick={handleClick}
    >
      {/* 批量选择复选框 */}
      {batchMode && isVerified && (
        <div className="absolute right-3 top-3">
          {selected
            ? <CheckSquare size={16} className="text-[var(--action-primary)]" />
            : <Square size={16} className="text-[var(--text-tertiary)]" />}
        </div>
      )}

      {/* 顶部：标题 + 状态点 */}
      <div className="flex items-start justify-between gap-2">
        <h4 className={`text-sm font-semibold leading-snug transition-colors ${
          selected ? "text-[var(--action-primary)]" : "text-[var(--text-primary)] group-hover:text-[var(--action-primary)]"
        }`}>
          {endpoint.label}
        </h4>
        {!batchMode && <StatusDot status={endpoint.status} />}
      </div>

      {/* 描述 */}
      <p className="mt-1.5 flex-1 text-xs leading-relaxed text-[var(--text-secondary)] line-clamp-2">
        {endpoint.description}
      </p>

      {/* 标签行 */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <MethodBadge method={endpoint.method} />
        {endpoint.cost_hint && (
          <span className="inline-flex items-center rounded border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] text-[var(--text-tertiary)]">
            💰 {endpoint.cost_hint}
          </span>
        )}
      </div>

      {/* 必填参数 */}
      {endpoint.required_params.length > 0 && (
        <div className="mt-2 text-[10px] text-[var(--text-tertiary)]">
          必填：{endpoint.required_params.join(" · ")}
        </div>
      )}

      {/* 采集按钮（单选模式 hover 显示） */}
      {isVerified && !batchMode && (
        <div className="mt-3 flex items-center justify-between">
          <span className="text-[10px] text-[var(--text-tertiary)]">{endpoint.platform}</span>
          <span className="flex items-center gap-0.5 text-[11px] font-semibold text-[var(--action-primary)] opacity-0 group-hover:opacity-100 transition-opacity">
            快速采集 <ChevronRight size={11} />
          </span>
        </div>
      )}

      {/* 批量模式平台标签 */}
      {isVerified && batchMode && (
        <div className="mt-3 text-[10px] text-[var(--text-tertiary)]">
          {endpoint.platform}
        </div>
      )}
    </div>
  );
}

/* 内容类型分组（第二层） */
function ContentTypeSection({
  contentType,
  endpoints,
  onCollect,
  batchMode,
  selectedEndpoints,
  onToggleSelect,
}: {
  contentType: string;
  endpoints: CollectorEndpoint[];
  onCollect: (ep: CollectorEndpoint) => void;
  batchMode: boolean;
  selectedEndpoints: Set<string>;
  onToggleSelect: (ep: CollectorEndpoint) => void;
}) {
  const meta = CONTENT_TYPE_META[contentType] ?? { label: contentType, emoji: "📦", desc: "" };
  const byMethod = endpoints.reduce<Record<string, CollectorEndpoint[]>>((acc, ep) => {
    (acc[ep.method] ??= []).push(ep);
    return acc;
  }, {});
  const methodOrder = ["tikhub", "apify", "github_api", "rss", "web_crawl"];

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] overflow-hidden">
      <div className="flex items-center gap-3 border-b border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-3">
        <span className="text-xl">{meta.emoji}</span>
        <div>
          <div className="text-sm font-semibold text-[var(--text-primary)]">{meta.label}</div>
          <div className="text-xs text-[var(--text-tertiary)]">{meta.desc}</div>
        </div>
        <span className="ml-auto text-xs font-medium text-[var(--text-tertiary)]">
          {endpoints.length} 个能力
        </span>
      </div>

      <div className="divide-y divide-[var(--border-subtle)]">
        {methodOrder
          .filter(m => byMethod[m])
          .map(method => {
            const eps = byMethod[method];
            const mm = METHOD_META[method] ?? { label: method, color: "", bg: "", icon: null };
            return (
              <div key={method} className="px-4 py-3">
                <div className={`mb-3 inline-flex items-center gap-1.5 rounded border px-2 py-1 text-xs font-semibold ${mm.bg} ${mm.color}`}>
                  {mm.icon}
                  {mm.label}
                  <span className="ml-1 rounded-full bg-white/60 px-1.5 py-px text-[10px]">
                    {eps.length}
                  </span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {eps.map(ep => (
                    <EndpointCard
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
          })}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   主页
───────────────────────────────────────────── */

export default function PlatformsPage() {
  const [activeEndpoint, setActiveEndpoint] = useState<CollectorEndpoint | null>(null);
  const [platformGroup, setPlatformGroup] = useState<string>("all");
  const [activeContentTypes, setActiveContentTypes] = useState<Set<string>>(new Set());
  const [activeMethods, setActiveMethods] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [batchMode, setBatchMode] = useState(false);
  const [selectedEndpoints, setSelectedEndpoints] = useState<Set<string>>(new Set());
  const [batchQueueIndex, setBatchQueueIndex] = useState<number>(0);
  const [batchQueue, setBatchQueue] = useState<CollectorEndpoint[]>([]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["collector-catalog"],
    queryFn: fetchCollectorCatalog,
  });

  const allEndpoints = useMemo(() => {
    if (!data) return [];
    return data.collectors.flatMap(c => c.endpoints).filter(e => e.status !== "disabled");
  }, [data]);

  const stats = useMemo(() => ({
    total: allEndpoints.filter(e => e.status === "verified").length,
    platforms: new Set(allEndpoints.map(e => e.platform)).size,
    content_types: new Set(allEndpoints.map(e => e.content_type)).size,
  }), [allEndpoints]);

  const filtered = useMemo(() => {
    let eps = allEndpoints;
    if (platformGroup !== "all") {
      const group = PLATFORM_GROUP_META[platformGroup];
      eps = eps.filter(e => group.platforms.some(p => e.platform.toLowerCase().includes(p)));
    }
    if (activeContentTypes.size > 0) {
      eps = eps.filter(e => activeContentTypes.has(e.content_type));
    }
    if (activeMethods.size > 0) {
      eps = eps.filter(e => activeMethods.has(e.method));
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      eps = eps.filter(e =>
        e.label.toLowerCase().includes(q) ||
        e.description.toLowerCase().includes(q) ||
        e.platform.toLowerCase().includes(q)
      );
    }
    return eps;
  }, [allEndpoints, platformGroup, activeContentTypes, activeMethods, search]);

  /* 按内容类型分组展示 */
  const byContentType = useMemo(() => {
    const map: Record<string, CollectorEndpoint[]> = {};
    for (const ep of filtered) {
      (map[ep.content_type] ??= []).push(ep);
    }
    // 固定顺序
    const order = ["post","comment","account","product","review","ad","search","trend","ai_answer","news","job","repo","feed","web_page"];
    return order.filter(k => map[k]).map(k => ({ type: k, endpoints: map[k] }));
  }, [filtered]);

  /* 可用的内容类型 / 方法选项（根据当前平台筛选动态变化） */
  const availableContentTypes = useMemo(() =>
    [...new Set(filtered.map(e => e.content_type))],
  [filtered]);
  const availableMethods = useMemo(() =>
    [...new Set(filtered.map(e => e.method))],
  [filtered]);

  function toggleContentType(ct: string) {
    setActiveContentTypes(prev => {
      const next = new Set(prev);
      next.has(ct) ? next.delete(ct) : next.add(ct);
      return next;
    });
  }
  function toggleMethod(m: string) {
    setActiveMethods(prev => {
      const next = new Set(prev);
      next.has(m) ? next.delete(m) : next.add(m);
      return next;
    });
  }
  function clearFilters() {
    setActiveContentTypes(new Set());
    setActiveMethods(new Set());
    setSearch("");
    setPlatformGroup("all");
  }
  function toggleBatchMode() {
    setBatchMode(prev => !prev);
    setSelectedEndpoints(new Set());
    setBatchQueue([]);
    setBatchQueueIndex(0);
  }
  function toggleSelect(ep: CollectorEndpoint) {
    setSelectedEndpoints(prev => {
      const next = new Set(prev);
      next.has(ep.endpoint_type) ? next.delete(ep.endpoint_type) : next.add(ep.endpoint_type);
      return next;
    });
  }
  function startBatchCollect() {
    const queue = allEndpoints.filter(ep => selectedEndpoints.has(ep.endpoint_type));
    if (queue.length === 0) return;
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

  const hasFilter = platformGroup !== "all" || activeContentTypes.size > 0 || activeMethods.size > 0 || search.trim();

  return (
    <AppShell
      title="平台能力中心"
      description={`按平台 · 内容类型 · 采集方式浏览 ${stats.total} 种数据采集能力`}
      brief="选择平台大类，找到所需数据类型，点击卡片立即启动采集"
    >
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="text-sm text-[var(--text-tertiary)]">加载采集能力目录…</div>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-[var(--state-danger)] bg-[var(--danger-soft)] p-8 text-center">
          <p className="text-sm text-[var(--state-danger)]">后端未连接，请先启动 API 服务</p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">{(error as Error).message}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">

          {/* ── 统计概览 ── */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "已验证采集能力", value: stats.total, unit: "个" },
              { label: "覆盖平台", value: stats.platforms, unit: "个" },
              { label: "数据类型", value: stats.content_types, unit: "种" },
            ].map(s => (
              <div key={s.label} className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-5 py-4">
                <div className="text-2xl font-bold text-[var(--text-primary)]">{s.value}<span className="ml-1 text-sm font-normal text-[var(--text-tertiary)]">{s.unit}</span></div>
                <div className="mt-0.5 text-xs text-[var(--text-tertiary)]">{s.label}</div>
              </div>
            ))}
          </div>

          {/* ── 批量采集控制栏 ── */}
          <div className="flex items-center gap-3">
            <button
              onClick={toggleBatchMode}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-all ${
                batchMode
                  ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                  : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--action-primary)] hover:text-[var(--action-primary)]"
              }`}
            >
              <CheckSquare size={14} />
              {batchMode ? "退出批量" : "批量采集"}
            </button>
            {batchMode && (
              <>
                <span className="text-sm text-[var(--text-tertiary)]">
                  已选 <span className="font-semibold text-[var(--text-primary)]">{selectedEndpoints.size}</span> 个
                </span>
                {selectedEndpoints.size > 0 && (
                  <button
                    onClick={startBatchCollect}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--action-primary)] px-3 py-1.5 text-sm font-semibold text-[var(--text-inverse)] hover:opacity-90"
                  >
                    <Play size={13} />
                    逐个启动 ({selectedEndpoints.size})
                  </button>
                )}
                {selectedEndpoints.size > 0 && (
                  <button
                    onClick={() => setSelectedEndpoints(new Set())}
                    className="text-xs text-[var(--text-tertiary)] hover:text-[var(--state-danger)]"
                  >
                    清空选择
                  </button>
                )}
              </>
            )}
          </div>

          {/* ── 第一层：平台大类 Tabs ── */}
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
              第一层：选择平台类别
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(PLATFORM_GROUP_META).map(([key, meta]) => {
                const count = key === "all"
                  ? allEndpoints.filter(e => e.status === "verified").length
                  : allEndpoints.filter(e => meta.platforms.some(p => e.platform.toLowerCase().includes(p))).length;
                return (
                  <button
                    key={key}
                    onClick={() => { setPlatformGroup(key); setActiveContentTypes(new Set()); setActiveMethods(new Set()); }}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-all
                      ${platformGroup === key
                        ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                        : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--action-primary)] hover:text-[var(--action-primary)]"
                      }`}
                  >
                    <span>{meta.emoji}</span>
                    <span>{meta.label}</span>
                    <span className={`rounded-full px-1.5 py-px text-[10px] font-bold ${platformGroup === key ? "bg-white/20" : "bg-[var(--surface-muted)]"}`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── 第二层筛选 + 搜索 ── */}
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-muted)] p-4">
            <div className="flex flex-wrap items-start gap-4">

              {/* 搜索框 */}
              <div className="relative flex-1 min-w-48">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
                <input
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="搜索采集能力…"
                  className="h-8 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] pl-8 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
                />
              </div>

              {/* 内容类型多选 */}
              <div className="flex flex-wrap gap-1.5 items-center">
                <span className="text-xs text-[var(--text-tertiary)] mr-1">内容类型：</span>
                {availableContentTypes.map(ct => {
                  const meta = CONTENT_TYPE_META[ct] ?? { label: ct, emoji: "📦", desc: "" };
                  const active = activeContentTypes.has(ct);
                  return (
                    <button
                      key={ct}
                      onClick={() => toggleContentType(ct)}
                      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium transition-all
                        ${active
                          ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                          : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--action-primary)]"
                        }`}
                    >
                      {meta.emoji} {meta.label}
                    </button>
                  );
                })}
              </div>

              {/* 采集方法多选 */}
              <div className="flex flex-wrap gap-1.5 items-center">
                <span className="text-xs text-[var(--text-tertiary)] mr-1">采集方式：</span>
                {availableMethods.map(m => {
                  const mm = METHOD_META[m] ?? { label: m, color: "", bg: "bg-gray-50 border-gray-200", icon: null };
                  const active = activeMethods.has(m);
                  return (
                    <button
                      key={m}
                      onClick={() => toggleMethod(m)}
                      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-semibold transition-all
                        ${active
                          ? `border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]`
                          : `${mm.bg} ${mm.color} hover:border-[var(--action-primary)]`
                        }`}
                    >
                      {mm.icon} {mm.label}
                    </button>
                  );
                })}
              </div>

              {/* 清空筛选 */}
              {hasFilter && (
                <button
                  onClick={clearFilters}
                  className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] px-2.5 py-1 text-xs text-[var(--text-tertiary)] hover:text-[var(--state-danger)] hover:border-[var(--state-danger)] transition-colors"
                >
                  <X size={11} /> 清空
                </button>
              )}
            </div>

            {/* 当前结果数 */}
            <div className="mt-3 text-xs text-[var(--text-tertiary)]">
              当前显示 <span className="font-semibold text-[var(--text-primary)]">{filtered.length}</span> 个采集能力
              {hasFilter && <span>（已筛选）</span>}
            </div>
          </div>

          {/* ── 第三层：按内容类型分组展示 ── */}
          {byContentType.length === 0 ? (
            <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-primary)] py-16 text-center">
              <p className="text-sm text-[var(--text-tertiary)]">没有匹配的采集能力</p>
              <button onClick={clearFilters} className="mt-3 text-xs text-[var(--action-primary)] underline">
                清空筛选
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {byContentType.map(({ type, endpoints }) => (
                <ContentTypeSection
                  key={type}
                  contentType={type}
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
