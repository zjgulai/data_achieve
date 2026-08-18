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

/* ─────────────────────────────────────────────────────────────
   Platform Logo
───────────────────────────────────────────────────────────── */

const PLATFORM_LOGOS: Record<string, { bg: string; fg: string; letter: string }> = {
  tiktok:        { bg: "#010101", fg: "#fff",    letter: "T"   },
  instagram:     { bg: "#E1306C", fg: "#fff",    letter: "In"  },
  xiaohongshu:   { bg: "#FF2442", fg: "#fff",    letter: "小"  },
  youtube:       { bg: "#FF0000", fg: "#fff",    letter: "YT"  },
  x:             { bg: "#000000", fg: "#fff",    letter: "X"   },
  facebook:      { bg: "#1877F2", fg: "#fff",    letter: "f"   },
  threads:       { bg: "#101010", fg: "#fff",    letter: "Th"  },
  pinterest:     { bg: "#E60023", fg: "#fff",    letter: "P"   },
  bluesky:       { bg: "#0085FF", fg: "#fff",    letter: "BS"  },
  telegram:      { bg: "#229ED9", fg: "#fff",    letter: "TG"  },
  reddit:        { bg: "#FF4500", fg: "#fff",    letter: "Re"  },
  lemon8:        { bg: "#FFD600", fg: "#000",    letter: "L8"  },
  snapchat:      { bg: "#FFFC00", fg: "#000",    letter: "SC"  },
  amazon:        { bg: "#FF9900", fg: "#131921", letter: "Az"  },
  walmart:       { bg: "#0071CE", fg: "#fff",    letter: "Wm"  },
  temu:          { bg: "#FF6B35", fg: "#fff",    letter: "Tm"  },
  shein:         { bg: "#000000", fg: "#fff",    letter: "SH"  },
  aliexpress:    { bg: "#FF6A00", fg: "#fff",    letter: "AE"  },
  tiktok_shop:   { bg: "#010101", fg: "#fff",    letter: "TKS" },
  ebay:          { bg: "#E53238", fg: "#fff",    letter: "eB"  },
  etsy:          { bg: "#F56400", fg: "#fff",    letter: "Et"  },
  shopify:       { bg: "#96BF48", fg: "#fff",    letter: "Sp"  },
  target:        { bg: "#CC0000", fg: "#fff",    letter: "Tg"  },
  trustpilot:    { bg: "#00B67A", fg: "#fff",    letter: "Tp"  },
  appstore:      { bg: "#0D84FF", fg: "#fff",    letter: "AS"  },
  google_play:   { bg: "#414141", fg: "#fff",    letter: "GP"  },
  tripadvisor:   { bg: "#34E0A1", fg: "#000",    letter: "TA"  },
  yelp:          { bg: "#D32323", fg: "#fff",    letter: "Yp"  },
  booking:       { bg: "#003580", fg: "#fff",    letter: "Bk"  },
  airbnb:        { bg: "#FF5A5F", fg: "#fff",    letter: "Ab"  },
  glassdoor:     { bg: "#0CAA41", fg: "#fff",    letter: "Gd"  },
  google:        { bg: "#4285F4", fg: "#fff",    letter: "G"   },
  google_search: { bg: "#4285F4", fg: "#fff",    letter: "G"   },
  google_trends: { bg: "#4285F4", fg: "#fff",    letter: "GT"  },
  google_news:   { bg: "#4285F4", fg: "#fff",    letter: "GN"  },
  google_maps:   { bg: "#34A853", fg: "#fff",    letter: "GM"  },
  chatgpt:       { bg: "#10A37F", fg: "#fff",    letter: "GPT" },
  perplexity:    { bg: "#20808D", fg: "#fff",    letter: "Px"  },
  gemini:        { bg: "#8E44AD", fg: "#fff",    letter: "Gm"  },
  facebook_ads:  { bg: "#1877F2", fg: "#fff",    letter: "Ads" },
  google_ads:    { bg: "#FBBC05", fg: "#000",    letter: "GAd" },
  tiktok_ads:    { bg: "#010101", fg: "#fff",    letter: "TAd" },
  snapchat_ads:  { bg: "#FFFC00", fg: "#000",    letter: "SA"  },
  pinterest_ads: { bg: "#E60023", fg: "#fff",    letter: "PA"  },
  linkedin:      { bg: "#0A66C2", fg: "#fff",    letter: "in"  },
  douyin:        { bg: "#010101", fg: "#fff",    letter: "抖"  },
  bilibili:      { bg: "#00A1D6", fg: "#fff",    letter: "B站" },
  weibo:         { bg: "#E6162D", fg: "#fff",    letter: "微"  },
  kuaishou:      { bg: "#FF4906", fg: "#fff",    letter: "快"  },
  wechat:        { bg: "#07C160", fg: "#fff",    letter: "微信" },
  zhihu:         { bg: "#0084FF", fg: "#fff",    letter: "知"  },
  product_hunt:  { bg: "#DA552F", fg: "#fff",    letter: "PH"  },
  crunchbase:    { bg: "#146AFF", fg: "#fff",    letter: "CB"  },
  hacker_news:   { bg: "#FF6600", fg: "#fff",    letter: "HN"  },
  indeed:        { bg: "#003A9B", fg: "#fff",    letter: "Id"  },
  github:        { bg: "#24292F", fg: "#fff",    letter: "GH"  },
  rss:           { bg: "#F26522", fg: "#fff",    letter: "RSS" },
  web:           { bg: "#4A5568", fg: "#fff",    letter: "Web" },
  ecommerce:     { bg: "#6B7280", fg: "#fff",    letter: "EC"  },
  regulatory:    { bg: "#D97706", fg: "#fff",    letter: "Reg" },
};

const PLATFORM_LABELS: Record<string, string> = {
  tiktok: "TikTok", instagram: "Instagram", youtube: "YouTube",
  x: "X (Twitter)", facebook: "Facebook", threads: "Threads",
  pinterest: "Pinterest", bluesky: "Bluesky", telegram: "Telegram",
  reddit: "Reddit", lemon8: "Lemon8", snapchat: "Snapchat",
  xiaohongshu: "小红书", linkedin: "LinkedIn",
  douyin: "抖音", bilibili: "B站", weibo: "微博",
  kuaishou: "快手", wechat: "微信", zhihu: "知乎",
  amazon: "Amazon", walmart: "Walmart", temu: "Temu",
  shein: "SHEIN", aliexpress: "AliExpress", tiktok_shop: "TikTok Shop",
  ebay: "eBay", etsy: "Etsy", shopify: "Shopify", target: "Target",
  ecommerce: "通用电商",
  trustpilot: "Trustpilot", appstore: "App Store",
  tripadvisor: "TripAdvisor", yelp: "Yelp", booking: "Booking",
  airbnb: "Airbnb", glassdoor: "Glassdoor",
  google_maps: "Google Maps", google_play: "Google Play",
  google_search: "Google Search", google_trends: "Google Trends",
  google_news: "Google News", chatgpt: "ChatGPT",
  perplexity: "Perplexity", gemini: "Gemini",
  facebook_ads: "Facebook Ads", google_ads: "Google Ads",
  tiktok_ads: "TikTok Ads", snapchat_ads: "Snapchat Ads",
  pinterest_ads: "Pinterest Ads",
  product_hunt: "Product Hunt", crunchbase: "Crunchbase",
  hacker_news: "Hacker News", indeed: "Indeed", github: "GitHub",
  regulatory: "监管机构", rss: "RSS", web: "Web 爬取",
};

function getPlatformMeta(platform: string) {
  return (
    PLATFORM_LOGOS[platform.toLowerCase()] ??
    { bg: "#786d6a", fg: "#fff", letter: platform.slice(0, 2).toUpperCase() }
  );
}

function getPlatformLabel(platform: string) {
  return PLATFORM_LABELS[platform.toLowerCase()] ?? platform.replace(/_/g, " ");
}

/* ─────────────────────────────────────────────────────────────
   Content Type labels
───────────────────────────────────────────────────────────── */

const CONTENT_TYPE_LABELS: Record<string, string> = {
  post:              "内容帖子",
  comment:           "用户评论",
  account:           "账号档案",
  product:           "商品信息",
  review:            "用户评价",
  ad:                "广告素材",
  job:               "招聘信息",
  news:              "新闻资讯",
  trend:             "搜索趋势",
  ai_answer:         "AI 回答",
  repo:              "代码仓库",
  feed:              "RSS 订阅",
  web_page:          "网页快照",
  web_page_markdown: "网页 Markdown",
  search:            "搜索结果",
  search_result:     "搜索结果",
  recall_notice:     "召回公告",
};

const CONTENT_TYPE_ORDER = [
  "post", "comment", "account", "product", "review", "ad",
  "search", "search_result", "trend", "ai_answer", "news", "job",
  "repo", "feed", "web_page", "web_page_markdown", "recall_notice",
];

/* ─────────────────────────────────────────────────────────────
   Method labels
───────────────────────────────────────────────────────────── */

const METHOD_LABELS: Record<string, string> = {
  tikhub:      "TikHub API",
  apify:       "Apify Actor",
  github_api:  "GitHub API",
  rss:         "RSS 解析",
  web_crawl:   "通用爬取",
  browser:     "浏览器采集",
  anysearch:   "AnySearch",
  jina_reader: "Jina Reader",
};

/* ─────────────────────────────────────────────────────────────
   Platform category tabs (top filter bar)
───────────────────────────────────────────────────────────── */

type CategoryKey =
  | "all"
  | "social_global"
  | "social_cn"
  | "ecommerce"
  | "review"
  | "search_ai"
  | "ads"
  | "b2b"
  | "regulatory"
  | "open_web";

const CATEGORIES: { key: CategoryKey; label: string; filterKeys: string[] }[] = [
  { key: "all",          label: "全部",      filterKeys: [] },
  {
    key: "social_global", label: "国际社媒",
    filterKeys: ["tiktok", "instagram", "youtube", "x", "facebook", "threads",
                 "pinterest", "bluesky", "telegram", "reddit", "lemon8",
                 "snapchat", "xiaohongshu", "linkedin"],
  },
  {
    key: "social_cn",    label: "中文社媒",
    filterKeys: ["douyin", "bilibili", "weibo", "kuaishou", "wechat", "zhihu"],
  },
  {
    key: "ecommerce",    label: "电商",
    filterKeys: ["amazon", "walmart", "temu", "shein", "aliexpress",
                 "tiktok_shop", "ebay", "etsy", "shopify", "target", "ecommerce"],
  },
  {
    key: "review",       label: "评价",
    filterKeys: ["trustpilot", "appstore", "tripadvisor", "yelp",
                 "booking", "airbnb", "glassdoor", "google_maps", "google_play"],
  },
  {
    key: "search_ai",    label: "搜索 & AI",
    filterKeys: ["google_search", "google_trends", "google_news",
                 "chatgpt", "perplexity", "gemini"],
  },
  {
    key: "ads",          label: "广告情报",
    filterKeys: ["facebook_ads", "google_ads", "tiktok_ads",
                 "snapchat_ads", "pinterest_ads"],
  },
  {
    key: "b2b",          label: "B2B & 开源",
    filterKeys: ["linkedin", "product_hunt", "crunchbase",
                 "hacker_news", "indeed", "github"],
  },
  {
    key: "regulatory",   label: "监管公告",
    filterKeys: ["regulatory"],
  },
  {
    key: "open_web",     label: "开放网络",
    filterKeys: ["rss", "web", "public_feed", "generic_web", "jina"],
  },
];

function matchCategory(platform: string, filterKeys: string[]): boolean {
  if (filterKeys.length === 0) return true;
  const p = platform.toLowerCase();
  return filterKeys.some(k => p.includes(k));
}

/* ─────────────────────────────────────────────────────────────
   Small atoms
───────────────────────────────────────────────────────────── */

function PlatformLogo({ platform, size = 48 }: { platform: string; size?: number }) {
  const meta = getPlatformMeta(platform);
  const radius = Math.round(size * 0.2);
  const fontSize = size >= 44 ? 13 : size >= 32 ? 11 : 9;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        borderRadius: radius,
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
      {meta.letter}
    </span>
  );
}

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
    "tikhub", "apify", "github_api", "anysearch",
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
