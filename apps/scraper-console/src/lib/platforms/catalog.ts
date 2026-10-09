/**
 * Shared platform / category metadata.
 *
 * Extracted from `app/platforms/page.tsx` so the capability center and the
 * datasets workspace render the same platform badges and category tabs.
 * Pure data + helpers only (no JSX); the badge component lives in
 * `components/platforms/platform-logo.tsx`.
 */

export type PlatformLogoMeta = { bg: string; fg: string; letter: string };

/* The brand hex values below are the one sanctioned exception to the
   "no raw hex" rule: letter badges are inline-styled because Tailwind
   arbitrary values cannot carry a per-brand palette. */
export const PLATFORM_LOGOS: Record<string, PlatformLogoMeta> = {
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
  baidu:         { bg: "#2932E1", fg: "#fff",    letter: "百"  },
  bing:          { bg: "#008373", fg: "#fff",    letter: "Bi"  },
  duckduckgo:    { bg: "#DE5833", fg: "#fff",    letter: "DDG" },
  devto:         { bg: "#0A0A0A", fg: "#fff",    letter: "DEV" },
  juejin:        { bg: "#1E80FF", fg: "#fff",    letter: "掘"  },
  substack:      { bg: "#FF6719", fg: "#fff",    letter: "Sub" },
  spiderfoot:    { bg: "#2D3748", fg: "#fff",    letter: "SF"  },
  firecrawl:     { bg: "#FF4F00", fg: "#fff",    letter: "FC"  },
  wappalyzer:    { bg: "#4608AD", fg: "#fff",    letter: "Wp"  },
  hackernews:    { bg: "#FF6600", fg: "#fff",    letter: "HN"  },
  npm:           { bg: "#CC3534", fg: "#fff",    letter: "npm" },
  pypi:          { bg: "#3775A9", fg: "#fff",    letter: "PyPI"},
  crates:        { bg: "#CE422B", fg: "#fff",    letter: "Rs"  },
  rubygems:      { bg: "#CC342D", fg: "#fff",    letter: "Gem" },
  golang:        { bg: "#00ACD7", fg: "#fff",    letter: "Go"  },
  packagist:     { bg: "#F28D1A", fg: "#fff",    letter: "PHP" },
  nuget:         { bg: "#004880", fg: "#fff",    letter: ".NET"},
  pubdev:        { bg: "#0175C2", fg: "#fff",    letter: "Dart"},
};

export const PLATFORM_LABELS: Record<string, string> = {
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
  baidu: "百度", bing: "Bing", duckduckgo: "DuckDuckGo",
  devto: "Dev.to", juejin: "掘金", substack: "Substack",
  spiderfoot: "SpiderFoot OSINT", firecrawl: "Firecrawl", wappalyzer: "技术栈检测",
  hackernews: "Hacker News", npm: "npm", pypi: "PyPI",
  crates: "crates.io", rubygems: "RubyGems", golang: "Go (pkg.go.dev)",
  packagist: "Packagist", nuget: "NuGet", pubdev: "pub.dev",
};

export function getPlatformMeta(platform: string): PlatformLogoMeta {
  return (
    PLATFORM_LOGOS[platform.toLowerCase()] ??
    { bg: "#786d6a", fg: "#fff", letter: platform.slice(0, 2).toUpperCase() }
  );
}

export function getPlatformLabel(platform: string): string {
  return PLATFORM_LABELS[platform.toLowerCase()] ?? platform.replace(/_/g, " ");
}

/* ── Content types ─────────────────────────────────────────── */

export const CONTENT_TYPE_LABELS: Record<string, string> = {
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
  osint_report:      "OSINT 报告",
};

export const CONTENT_TYPE_ORDER = [
  "post", "comment", "account", "product", "review", "ad",
  "search", "search_result", "trend", "ai_answer", "news", "job",
  "repo", "feed", "web_page", "web_page_markdown", "recall_notice", "osint_report",
];

export function getContentTypeLabel(contentType: string): string {
  return CONTENT_TYPE_LABELS[contentType] ?? contentType;
}

/* ── Collection methods ────────────────────────────────────── */

export const METHOD_LABELS: Record<string, string> = {
  tikhub:        "TikHub API",
  apify:         "Apify Actor",
  github_api:    "GitHub API",
  rss:           "RSS 解析",
  web_crawl:     "通用爬取",
  browser:       "浏览器采集",
  anysearch:     "AnySearch",
  exa:           "Exa AI Search",
  jina_reader:   "Jina Reader",
  mediacrawler:  "MediaCrawler",
  serp:          "搜索引擎 SERP",
  firecrawl:     "Firecrawl",
  osint:         "OSINT 情报",
  tech_stack:    "技术栈识别",
};

/* ── Category tabs ─────────────────────────────────────────── */

export type CategoryKey =
  | "all"
  | "social_global"
  | "social_cn"
  | "ecommerce"
  | "review"
  | "search_ai"
  | "ads"
  | "b2b"
  | "regulatory"
  | "open_web"
  | "search_cn"
  | "osint_tools";

export const CATEGORIES: { key: CategoryKey; label: string; filterKeys: string[] }[] = [
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
    key: "search_cn",    label: "中文搜索",
    filterKeys: ["baidu", "bing", "duckduckgo"],
  },
  {
    key: "ads",          label: "广告情报",
    filterKeys: ["facebook_ads", "google_ads", "tiktok_ads",
                 "snapchat_ads", "pinterest_ads"],
  },
  {
    key: "b2b",          label: "B2B & 开源",
    filterKeys: ["linkedin", "product_hunt", "crunchbase",
                 "hacker_news", "indeed", "github", "devto", "juejin", "substack"],
  },
  {
    key: "regulatory",   label: "监管公告",
    filterKeys: ["regulatory"],
  },
  {
    key: "open_web",     label: "开放网络",
    filterKeys: ["rss", "web", "public_feed", "generic_web", "jina",
                 "firecrawl", "wappalyzer"],
  },
  {
    key: "osint_tools",  label: "OSINT 情报",
    filterKeys: ["osint", "sherlock", "maigret", "twscrape", "spiderfoot"],
  },
];

export function matchCategory(platform: string, filterKeys: string[]): boolean {
  if (filterKeys.length === 0) return true;
  const p = platform.toLowerCase();
  return filterKeys.some(k => p.includes(k));
}

export function categoryLabel(key: CategoryKey): string {
  return CATEGORIES.find(c => c.key === key)?.label ?? key;
}

/** Backend `AutomationProductDatasetListItemResponse.category` values. */
const DATASET_TYPE_CATEGORY: Record<string, CategoryKey> = {
  ecommerce_product: "ecommerce",
  public_content_update: "open_web",
  github_tool_radar: "osint_tools",
};

/**
 * Resolve a dataset's category tab.
 *
 * Prefers the real platforms derived server-side from the originating
 * endpoint; falls back to the coarse `category` the backend derives from
 * `dataset_type`. Returns `"all"` when nothing matches.
 */
export function categoryKeyForPlatforms(
  platforms: string[],
  fallbackCategory?: string | null,
): CategoryKey {
  const normalized = platforms.map(p => p.toLowerCase()).filter(Boolean);
  if (normalized.length > 0) {
    const hit = CATEGORIES.find(
      c => c.key !== "all" && normalized.some(p => c.filterKeys.includes(p)),
    );
    if (hit) return hit.key;
    // loose fallback for platform keys not listed verbatim in filterKeys
    const loose = CATEGORIES.find(
      c => c.key !== "all" && normalized.some(p => matchCategory(p, c.filterKeys)),
    );
    if (loose) return loose.key;
  }
  if (fallbackCategory && CATEGORY_KEYS.has(fallbackCategory)) {
    return fallbackCategory as CategoryKey;
  }
  return "all";
}

const CATEGORY_KEYS = new Set<string>(CATEGORIES.map(c => c.key));

export function datasetCategory(
  platforms: string[],
  datasetType: string,
): CategoryKey {
  return categoryKeyForPlatforms(platforms, DATASET_TYPE_CATEGORY[datasetType] ?? null);
}
