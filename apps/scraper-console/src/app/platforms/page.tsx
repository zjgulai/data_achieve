"use client";

import { useState, useMemo } from "react";
import {
  Search, X, ChevronRight, Zap, Database, Globe, Rss, GitFork,
  CheckSquare, Square, Play, Monitor, ShoppingCart, Star, Megaphone,
  Briefcase, Newspaper, TrendingUp, Bot, Code2, Radio, FileText,
  LayoutGrid, Users, Building2, ShieldAlert, Link, MessageSquare,
  Hash, BarChart2, Package, Layers, Filter, SlidersHorizontal,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { QuickCollectDrawer } from "@/components/platforms/quick-collect-drawer";
import { fetchCollectorCatalog } from "@/lib/api/collectors";
import type { CollectorEndpoint } from "@/lib/api/collectors";
import { useQuery } from "@tanstack/react-query";

/* ─────────────────────────────────────────────
   平台 Logo SVG 映射
   每个平台使用品牌原色 SVG path，fallback 为首字母
───────────────────────────────────────────── */

const PLATFORM_LOGOS: Record<string, { bg: string; fg: string; path?: string; letter?: string }> = {
  tiktok:        { bg: "#010101", fg: "#fff", letter: "T" },
  instagram:     { bg: "#E1306C", fg: "#fff", letter: "In" },
  xiaohongshu:   { bg: "#FF2442", fg: "#fff", letter: "小" },
  youtube:       { bg: "#FF0000", fg: "#fff", letter: "YT" },
  x:             { bg: "#000000", fg: "#fff", letter: "𝕏" },
  facebook:      { bg: "#1877F2", fg: "#fff", letter: "f" },
  threads:       { bg: "#101010", fg: "#fff", letter: "Th" },
  pinterest:     { bg: "#E60023", fg: "#fff", letter: "P" },
  bluesky:       { bg: "#0085FF", fg: "#fff", letter: "BS" },
  telegram:      { bg: "#229ED9", fg: "#fff", letter: "TG" },
  reddit:        { bg: "#FF4500", fg: "#fff", letter: "Re" },
  lemon8:        { bg: "#FFD600", fg: "#000", letter: "L8" },
  snapchat:      { bg: "#FFFC00", fg: "#000", letter: "SC" },
  amazon:        { bg: "#FF9900", fg: "#131921", letter: "Az" },
  walmart:       { bg: "#0071CE", fg: "#fff", letter: "Wm" },
  temu:          { bg: "#FF6B35", fg: "#fff", letter: "Tm" },
  shein:         { bg: "#000000", fg: "#fff", letter: "SH" },
  aliexpress:    { bg: "#FF6A00", fg: "#fff", letter: "AE" },
  tiktok_shop:   { bg: "#010101", fg: "#fff", letter: "TKS" },
  ebay:          { bg: "#E53238", fg: "#fff", letter: "eB" },
  etsy:          { bg: "#F56400", fg: "#fff", letter: "Et" },
  shopify:       { bg: "#96BF48", fg: "#fff", letter: "Sp" },
  target:        { bg: "#CC0000", fg: "#fff", letter: "Tg" },
  trustpilot:    { bg: "#00B67A", fg: "#fff", letter: "Tp" },
  appstore:      { bg: "#0D84FF", fg: "#fff", letter: "AS" },
  google_play:   { bg: "#414141", fg: "#fff", letter: "GP" },
  tripadvisor:   { bg: "#34E0A1", fg: "#000", letter: "TA" },
  yelp:          { bg: "#D32323", fg: "#fff", letter: "Yp" },
  booking:       { bg: "#003580", fg: "#fff", letter: "Bk" },
  airbnb:        { bg: "#FF5A5F", fg: "#fff", letter: "Ab" },
  glassdoor:     { bg: "#0CAA41", fg: "#fff", letter: "Gd" },
  google:        { bg: "#4285F4", fg: "#fff", letter: "G" },
  google_search: { bg: "#4285F4", fg: "#fff", letter: "G" },
  google_trends: { bg: "#4285F4", fg: "#fff", letter: "GT" },
  google_news:   { bg: "#4285F4", fg: "#fff", letter: "GN" },
  google_maps:   { bg: "#34A853", fg: "#fff", letter: "GM" },
  chatgpt:       { bg: "#10A37F", fg: "#fff", letter: "GPT" },
  perplexity:    { bg: "#20808D", fg: "#fff", letter: "Px" },
  gemini:        { bg: "#8E44AD", fg: "#fff", letter: "Gm" },
  facebook_ads:  { bg: "#1877F2", fg: "#fff", letter: "Ads" },
  google_ads:    { bg: "#FBBC05", fg: "#000", letter: "GAd" },
  tiktok_ads:    { bg: "#010101", fg: "#fff", letter: "TAd" },
  snapchat_ads:  { bg: "#FFFC00", fg: "#000", letter: "SA" },
  pinterest_ads: { bg: "#E60023", fg: "#fff", letter: "PA" },
  linkedin:      { bg: "#0A66C2", fg: "#fff", letter: "in" },
  product_hunt:  { bg: "#DA552F", fg: "#fff", letter: "PH" },
  crunchbase:    { bg: "#146AFF", fg: "#fff", letter: "CB" },
  hacker_news:   { bg: "#FF6600", fg: "#fff", letter: "HN" },
  indeed:        { bg: "#003A9B", fg: "#fff", letter: "Id" },
  github:        { bg: "#24292F", fg: "#fff", letter: "GH" },
  rss:           { bg: "#F26522", fg: "#fff", letter: "RSS" },
  web:           { bg: "#4A5568", fg: "#fff", letter: "Web" },
  ecommerce:     { bg: "#6B7280", fg: "#fff", letter: "EC" },
  regulatory:    { bg: "#D97706", fg: "#fff", letter: "Reg" },
};

function PlatformLogo({ platform, size = 20 }: { platform: string; size?: number }) {
  const meta = PLATFORM_LOGOS[platform.toLowerCase()] ?? { bg: "#786d6a", fg: "#fff", letter: platform.slice(0, 2).toUpperCase() };
  const fontSize = size <= 16 ? 7 : size <= 20 ? 8 : 10;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        borderRadius: 4,
        background: meta.bg,
        color: meta.fg,
        fontSize,
        fontWeight: 700,
        lineHeight: 1,
        flexShrink: 0,
        letterSpacing: "-0.03em",
        fontFamily: "var(--font-sans)",
      }}
    >
      {meta.letter ?? platform.slice(0, 2).toUpperCase()}
    </span>
  );
}

/* ─────────────────────────────────────────────
   内容类型元数据（Lucide 图标，无 emoji）
───────────────────────────────────────────── */

const CONTENT_TYPE_META: Record<string, { label: string; icon: React.ReactNode; desc: string }> = {
  post:              { label: "内容帖子",      icon: <Hash size={13} />,          desc: "视频、图文、推文等 UGC 内容" },
  comment:           { label: "用户评论",      icon: <MessageSquare size={13} />, desc: "帖子下的用户互动评论" },
  account:           { label: "账号档案",      icon: <Users size={13} />,         desc: "品牌/KOL 账号主页信息" },
  product:           { label: "商品信息",      icon: <ShoppingCart size={13} />,  desc: "电商平台商品详情与上架数据" },
  review:            { label: "用户评价",      icon: <Star size={13} />,          desc: "电商、地图、应用商店评价" },
  ad:                { label: "广告素材",      icon: <Megaphone size={13} />,     desc: "各平台在投广告创意与数据" },
  job:               { label: "招聘信息",      icon: <Briefcase size={13} />,     desc: "职位招聘与人才市场数据" },
  news:              { label: "新闻资讯",      icon: <Newspaper size={13} />,     desc: "媒体报道与行业新闻" },
  trend:             { label: "搜索趋势",      icon: <TrendingUp size={13} />,    desc: "关键词热度与时间趋势" },
  ai_answer:         { label: "AI 回答",       icon: <Bot size={13} />,           desc: "ChatGPT / Perplexity / Gemini 搜索结果" },
  repo:              { label: "代码仓库",      icon: <Code2 size={13} />,         desc: "GitHub 仓库与技术话题" },
  feed:              { label: "RSS 订阅",      icon: <Radio size={13} />,         desc: "标准 RSS / Atom 订阅源" },
  web_page:          { label: "网页快照",      icon: <Globe size={13} />,         desc: "任意公开网页抓取与 RAG 解析" },
  search:            { label: "搜索结果",      icon: <Search size={13} />,        desc: "搜索引擎关键词结果页" },
  search_result:     { label: "搜索结果",      icon: <Search size={13} />,        desc: "AnySearch / 通用搜索 API 结果" },
  web_page_markdown: { label: "网页 Markdown", icon: <FileText size={13} />,      desc: "Jina Reader 页面转 Markdown 内容" },
  recall_notice:     { label: "召回公告",      icon: <ShieldAlert size={13} />,   desc: "监管机构产品召回与安全预警" },
};

/* ─────────────────────────────────────────────
   采集方法元数据（去彩色背景，用 token）
───────────────────────────────────────────── */

const METHOD_META: Record<string, { label: string; icon: React.ReactNode }> = {
  tikhub:      { label: "TikHub API",    icon: <Zap size={11} /> },
  apify:       { label: "Apify Actor",   icon: <Database size={11} /> },
  github_api:  { label: "GitHub API",    icon: <GitFork size={11} /> },
  rss:         { label: "RSS 解析",      icon: <Rss size={11} /> },
  web_crawl:   { label: "通用爬取",      icon: <Globe size={11} /> },
  browser:     { label: "浏览器采集",    icon: <Monitor size={11} /> },
  anysearch:   { label: "AnySearch",     icon: <Search size={11} /> },
  jina_reader: { label: "Jina Reader",   icon: <Link size={11} /> },
};

/* ─────────────────────────────────────────────
   平台分组（Lucide 图标，无 emoji）
───────────────────────────────────────────── */

type PlatformGroupKey = "all" | "social" | "ecommerce" | "review" | "search" | "ads" | "b2b" | "regulatory" | "open_web";

const PLATFORM_GROUP_META: Record<PlatformGroupKey, {
  label: string;
  icon: React.ReactNode;
  platforms: string[];
}> = {
  all:        { label: "全部",       icon: <LayoutGrid size={14} />,  platforms: [] },
  social:     { label: "社交媒体",   icon: <Hash size={14} />,        platforms: ["tiktok","instagram","xiaohongshu","youtube","x","facebook","threads","pinterest","bluesky","telegram","reddit","lemon8","snapchat"] },
  ecommerce:  { label: "电商平台",   icon: <ShoppingCart size={14} />, platforms: ["amazon","walmart","temu","shein","aliexpress","tiktok_shop","ebay","etsy","shopify","target"] },
  review:     { label: "评价平台",   icon: <Star size={14} />,        platforms: ["trustpilot","appstore","tripadvisor","yelp","booking","airbnb","glassdoor","google_maps","google_play"] },
  search:     { label: "搜索 & AI",  icon: <Bot size={14} />,         platforms: ["google","google_search","google_trends","google_news","google_maps","chatgpt","perplexity","gemini"] },
  ads:        { label: "广告情报",   icon: <Megaphone size={14} />,   platforms: ["facebook_ads","google_ads","tiktok_ads","snapchat_ads","pinterest_ads"] },
  b2b:        { label: "B2B & 开源", icon: <Building2 size={14} />,   platforms: ["linkedin","glassdoor","product_hunt","crunchbase","hacker_news","indeed","github"] },
  regulatory: { label: "监管公告",   icon: <ShieldAlert size={14} />, platforms: ["regulatory"] },
  open_web:   { label: "开放网络",   icon: <Globe size={14} />,       platforms: ["rss","web","public_feed","generic_web","ecommerce"] },
};

/* ─────────────────────────────────────────────
   工具函数
───────────────────────────────────────────── */

function getPlatformGroup(platform: string): PlatformGroupKey {
  for (const [key, meta] of Object.entries(PLATFORM_GROUP_META)) {
    if (key === "all") continue;
    if (meta.platforms.some(p => platform.toLowerCase().includes(p))) return key as PlatformGroupKey;
  }
  return "open_web";
}

/* ─────────────────────────────────────────────
   子组件
───────────────────────────────────────────── */

function StatusDot({ status }: { status: string }) {
  if (status === "verified") return <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--state-success)]" />;
  if (status === "pending")  return <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--state-warning)]" />;
  return <span className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--border-strong)]" />;
}

function MethodBadge({ method }: { method: string }) {
  const m = METHOD_META[method] ?? { label: method, icon: <Globe size={11} /> };
  return (
    <span className="inline-flex items-center gap-1 rounded border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
      {m.icon}
      {m.label}
    </span>
  );
}

/* 采集行（工业风行式布局替代卡片堆叠） */
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
      role="row"
      onClick={handleClick}
      className={[
        "group flex items-center gap-3 border-b border-[var(--border-subtle)] px-4 py-2.5 transition-colors last:border-b-0",
        isVerified
          ? selected
            ? "bg-[var(--accent-1-soft)] cursor-pointer"
            : "hover:bg-[var(--surface-muted)] cursor-pointer"
          : "opacity-50 cursor-default",
      ].join(" ")}
    >
      {/* 批量选择 */}
      {batchMode && isVerified && (
        <div className="flex-shrink-0 text-[var(--text-tertiary)]">
          {selected
            ? <CheckSquare size={14} className="text-[var(--action-primary)]" />
            : <Square size={14} />}
        </div>
      )}

      {/* 平台 logo */}
      <PlatformLogo platform={endpoint.platform} size={20} />

      {/* 主内容 */}
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className={[
            "text-sm font-medium leading-snug truncate",
            selected ? "text-[var(--action-primary)]" : "text-[var(--text-primary)] group-hover:text-[var(--action-primary)]",
          ].join(" ")}>
            {endpoint.label}
          </span>
          {!batchMode && <StatusDot status={endpoint.status} />}
        </div>
        <p className="truncate text-xs text-[var(--text-tertiary)]">
          {endpoint.description}
        </p>
      </div>

      {/* 必填参数 */}
      {endpoint.required_params.length > 0 && (
        <div className="hidden lg:flex items-center gap-1 flex-shrink-0">
          {endpoint.required_params.slice(0, 3).map(p => (
            <span key={p} className="rounded border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] text-[var(--text-tertiary)]">
              {p}
            </span>
          ))}
          {endpoint.required_params.length > 3 && (
            <span className="text-[10px] text-[var(--text-tertiary)]">+{endpoint.required_params.length - 3}</span>
          )}
        </div>
      )}

      {/* 方法 badge */}
      <div className="flex-shrink-0">
        <MethodBadge method={endpoint.method} />
      </div>

      {/* 费用 */}
      {endpoint.cost_hint && (
        <span className="flex-shrink-0 hidden md:inline-flex items-center rounded border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-1.5 py-0.5 text-[10px] text-[var(--text-tertiary)]">
          {endpoint.cost_hint}
        </span>
      )}

      {/* 采集箭头 */}
      {isVerified && !batchMode && (
        <ChevronRight
          size={14}
          className="flex-shrink-0 text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity"
        />
      )}
    </div>
  );
}

/* 内容类型分组面板 */
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
  const meta = CONTENT_TYPE_META[contentType] ?? { label: contentType, icon: <Package size={13} />, desc: "" };

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
      {/* 面板标题行 */}
      <div className="flex items-center gap-2.5 border-b border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-2.5">
        <span className="text-[var(--text-secondary)]">{meta.icon}</span>
        <span className="text-sm font-semibold text-[var(--text-primary)]">{meta.label}</span>
        <span className="text-xs text-[var(--text-tertiary)]">{meta.desc}</span>
        <span className="ml-auto text-xs font-medium tabular-nums text-[var(--text-tertiary)]">
          {endpoints.length}
        </span>
      </div>

      {/* 行列表 */}
      <div role="rowgroup">
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

/* ─────────────────────────────────────────────
   主页
───────────────────────────────────────────── */

export default function PlatformsPage() {
  const [activeEndpoint, setActiveEndpoint] = useState<CollectorEndpoint | null>(null);
  const [platformGroup, setPlatformGroup] = useState<PlatformGroupKey>("all");
  const [activeContentTypes, setActiveContentTypes] = useState<Set<string>>(new Set());
  const [activeMethods, setActiveMethods] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [batchMode, setBatchMode] = useState(false);
  const [selectedEndpoints, setSelectedEndpoints] = useState<Set<string>>(new Set());
  const [batchQueueIndex, setBatchQueueIndex] = useState(0);
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
    total:     allEndpoints.filter(e => e.status === "verified").length,
    platforms: new Set(allEndpoints.map(e => e.platform)).size,
    types:     new Set(allEndpoints.map(e => e.content_type)).size,
  }), [allEndpoints]);

  const filtered = useMemo(() => {
    let eps = allEndpoints;
    if (platformGroup !== "all") {
      const group = PLATFORM_GROUP_META[platformGroup];
      eps = eps.filter(e => group.platforms.some(p => e.platform.toLowerCase().includes(p)));
    }
    if (activeContentTypes.size > 0) eps = eps.filter(e => activeContentTypes.has(e.content_type));
    if (activeMethods.size > 0) eps = eps.filter(e => activeMethods.has(e.method));
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

  const byContentType = useMemo(() => {
    const map: Record<string, CollectorEndpoint[]> = {};
    for (const ep of filtered) (map[ep.content_type] ??= []).push(ep);
    const order = ["post","comment","account","product","review","ad","search","search_result","trend","ai_answer","news","job","repo","feed","web_page","web_page_markdown","recall_notice"];
    return order.filter(k => map[k]).map(k => ({ type: k, endpoints: map[k] }));
  }, [filtered]);

  const availableContentTypes = useMemo(() => [...new Set(filtered.map(e => e.content_type))], [filtered]);
  const availableMethods      = useMemo(() => [...new Set(filtered.map(e => e.method))], [filtered]);

  function toggleContentType(ct: string) {
    setActiveContentTypes(prev => { const n = new Set(prev); n.has(ct) ? n.delete(ct) : n.add(ct); return n; });
  }
  function toggleMethod(m: string) {
    setActiveMethods(prev => { const n = new Set(prev); n.has(m) ? n.delete(m) : n.add(m); return n; });
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
    setSelectedEndpoints(prev => { const n = new Set(prev); n.has(ep.endpoint_type) ? n.delete(ep.endpoint_type) : n.add(ep.endpoint_type); return n; });
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
    if (next < batchQueue.length) { setBatchQueueIndex(next); setActiveEndpoint(batchQueue[next]); }
    else { setBatchQueue([]); setBatchQueueIndex(0); }
  }

  const hasFilter = platformGroup !== "all" || activeContentTypes.size > 0 || activeMethods.size > 0 || search.trim();

  return (
    <AppShell
      title="平台能力中心"
      description={`${stats.total} 种已验证采集能力 · ${stats.platforms} 个平台 · ${stats.types} 种数据类型`}
      brief="选择平台类别，找到所需数据，点击行立即启动采集"
    >
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <span className="text-sm text-[var(--text-tertiary)]">加载采集能力目录…</span>
        </div>
      ) : error ? (
        <div className="rounded-lg border border-[var(--state-danger)] bg-[var(--danger-soft)] p-8 text-center">
          <p className="text-sm font-medium text-[var(--state-danger)]">后端未连接，请先启动 API 服务</p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)]">{(error as Error).message}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-5">

          {/* ── 统计概览 ── */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "已验证采集能力", value: stats.total,     unit: "个" },
              { label: "覆盖平台",       value: stats.platforms, unit: "个" },
              { label: "数据类型",       value: stats.types,     unit: "种" },
            ].map(s => (
              <div key={s.label} className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-4 py-3">
                <div className="flex items-baseline gap-1">
                  <span className="text-2xl font-semibold tabular-nums text-[var(--text-primary)]">{s.value}</span>
                  <span className="text-xs text-[var(--text-tertiary)]">{s.unit}</span>
                </div>
                <div className="mt-0.5 text-xs text-[var(--text-tertiary)]">{s.label}</div>
              </div>
            ))}
          </div>

          {/* ── 批量操作栏 ── */}
          <div className="flex items-center gap-3">
            <button
              onClick={toggleBatchMode}
              className={[
                "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                batchMode
                  ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                  : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]",
              ].join(" ")}
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
                    className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--action-primary)] px-3 py-1.5 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] transition-colors"
                  >
                    <Play size={13} />
                    逐个启动 ({selectedEndpoints.size})
                  </button>
                )}
                {selectedEndpoints.size > 0 && (
                  <button
                    onClick={() => setSelectedEndpoints(new Set())}
                    className="text-xs text-[var(--text-tertiary)] hover:text-[var(--state-danger)] transition-colors"
                  >
                    清空选择
                  </button>
                )}
              </>
            )}
          </div>

          {/* ── 平台大类 Tab ── */}
          <div>
            <div className="mb-2 text-xs font-medium text-[var(--text-tertiary)]">平台类别</div>
            <div className="flex flex-wrap gap-1.5">
              {(Object.entries(PLATFORM_GROUP_META) as [PlatformGroupKey, typeof PLATFORM_GROUP_META[PlatformGroupKey]][]).map(([key, meta]) => {
                const count = key === "all"
                  ? allEndpoints.filter(e => e.status === "verified").length
                  : allEndpoints.filter(e => meta.platforms.some(p => e.platform.toLowerCase().includes(p))).length;
                const active = platformGroup === key;
                return (
                  <button
                    key={key}
                    onClick={() => { setPlatformGroup(key); setActiveContentTypes(new Set()); setActiveMethods(new Set()); }}
                    className={[
                      "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors",
                      active
                        ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                        : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]",
                    ].join(" ")}
                  >
                    <span className={active ? "text-[var(--text-inverse)]" : "text-[var(--text-tertiary)]"}>
                      {meta.icon}
                    </span>
                    <span>{meta.label}</span>
                    <span className={[
                      "rounded px-1.5 py-px text-[10px] font-bold tabular-nums",
                      active ? "bg-white/20 text-[var(--text-inverse)]" : "bg-[var(--surface-muted)] text-[var(--text-tertiary)]",
                    ].join(" ")}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── 筛选栏 ── */}
          <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-muted)] px-4 py-3">
            <div className="flex flex-wrap items-start gap-3">

              {/* 搜索框 */}
              <div className="relative min-w-48 flex-1">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
                <input
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="搜索采集能力…"
                  className="h-8 w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] pl-8 pr-3 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-1)]"
                />
              </div>

              {/* 内容类型 */}
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="flex items-center gap-1 text-xs text-[var(--text-tertiary)]">
                  <Filter size={11} /> 类型：
                </span>
                {availableContentTypes.map(ct => {
                  const m = CONTENT_TYPE_META[ct] ?? { label: ct, icon: <Package size={11} />, desc: "" };
                  const active = activeContentTypes.has(ct);
                  return (
                    <button
                      key={ct}
                      onClick={() => toggleContentType(ct)}
                      className={[
                        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium transition-colors",
                        active
                          ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                          : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]",
                      ].join(" ")}
                    >
                      {m.icon} {m.label}
                    </button>
                  );
                })}
              </div>

              {/* 采集方式 */}
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="flex items-center gap-1 text-xs text-[var(--text-tertiary)]">
                  <SlidersHorizontal size={11} /> 方式：
                </span>
                {availableMethods.map(m => {
                  const mm = METHOD_META[m] ?? { label: m, icon: <Globe size={11} /> };
                  const active = activeMethods.has(m);
                  return (
                    <button
                      key={m}
                      onClick={() => toggleMethod(m)}
                      className={[
                        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium transition-colors",
                        active
                          ? "border-[var(--action-primary)] bg-[var(--action-primary)] text-[var(--text-inverse)]"
                          : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:border-[var(--border-strong)]",
                      ].join(" ")}
                    >
                      {mm.icon} {mm.label}
                    </button>
                  );
                })}
              </div>

              {/* 清空 */}
              {hasFilter && (
                <button
                  onClick={clearFilters}
                  className="inline-flex items-center gap-1 rounded border border-[var(--border-subtle)] px-2 py-0.5 text-xs text-[var(--text-tertiary)] hover:border-[var(--state-danger)] hover:text-[var(--state-danger)] transition-colors"
                >
                  <X size={11} /> 清空
                </button>
              )}
            </div>

            <div className="mt-2 text-xs text-[var(--text-tertiary)]">
              显示 <span className="font-semibold tabular-nums text-[var(--text-primary)]">{filtered.length}</span> 个采集能力
              {hasFilter && <span className="ml-1">(已筛选)</span>}
            </div>
          </div>

          {/* ── 内容类型分组 ── */}
          {byContentType.length === 0 ? (
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] py-16 text-center">
              <p className="text-sm text-[var(--text-tertiary)]">没有匹配的采集能力</p>
              <button onClick={clearFilters} className="mt-2 text-xs text-[var(--action-primary)] underline">
                清空筛选
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
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
