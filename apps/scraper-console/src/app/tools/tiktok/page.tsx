"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  Database,
  FileText,
  KeyRound,
  Loader2,
  Play,
  Search,
  TrendingUp,
  Users,
  X,
} from "lucide-react";
import { AppShell } from "@/components/layout/app-shell";
import { StatTile } from "@/components/ui/stat-tile";
import { ApiError } from "@/lib/api/client";
import { updateCredential } from "@/lib/api/credentials";
import { fetchProjects } from "@/lib/api/projects";
import {
  runTikTokTool,
  type TikTokToolResult,
  type TikTokToolRun,
} from "@/lib/api/tiktok-tools";

type Tab = "trends" | "videos" | "creators" | "products";
type VideoMode = "search" | "hashtag" | "detail" | "comments";
type CreatorMode = "profile" | "search";
type ProductMode =
  | "search"
  | "detail"
  | "reviews"
  | "video_products"
  | "creator_showcase";

type Column = { key: string; label: string };

const COUNTRIES = [
  { value: "US", label: "美国" },
  { value: "GB", label: "英国" },
  { value: "CA", label: "加拿大" },
  { value: "AU", label: "澳大利亚" },
  { value: "DE", label: "德国" },
];

const PERIODS = [
  { value: 7, label: "近 7 天" },
  { value: 30, label: "近 30 天" },
  { value: 90, label: "近 90 天" },
];

const VIDEO_COLUMNS: Column[] = [
  { key: "video_id", label: "视频 ID" },
  { key: "text", label: "文案" },
  { key: "author_username", label: "作者" },
  { key: "play_count", label: "播放" },
  { key: "like_count", label: "点赞" },
  { key: "comment_count", label: "评论" },
  { key: "created_at", label: "发布时间" },
];

const COMMENTS_COLUMNS: Column[] = [
  { key: "text", label: "评论" },
  { key: "author_nickname", label: "评论者" },
  { key: "like_count", label: "点赞" },
  { key: "reply_count", label: "回复" },
  { key: "is_pinned", label: "置顶" },
  { key: "creator_interacted", label: "作者互动" },
];

function columnsFor(toolId?: string): Column[] {
  if (toolId === "tiktok_trend_rank") {
    return [
      { key: "rank", label: "排名" },
      { key: "name", label: "话题" },
      { key: "post_count", label: "帖子数" },
      { key: "view_count", label: "播放量" },
      { key: "entity_id", label: "话题 ID" },
    ];
  }
  if (toolId === "tiktok_video_comments") return COMMENTS_COLUMNS;
  if (toolId === "tiktok_creator_profile") {
    return [
      { key: "unique_id", label: "账号" },
      { key: "nickname", label: "昵称" },
      { key: "follower_count", label: "粉丝" },
      { key: "following_count", label: "关注" },
      { key: "video_count", label: "作品" },
    ];
  }
  if (toolId === "tiktok_creator_search") {
    return [
      { key: "unique_id", label: "账号" },
      { key: "nickname", label: "昵称" },
      { key: "uid", label: "UID" },
    ];
  }
  if (toolId === "tiktok_transcript") {
    return [
      { key: "video_id", label: "视频 ID" },
      { key: "language", label: "语言" },
      { key: "text", label: "字幕/转写" },
    ];
  }
  if (toolId === "tiktok_product_reviews") {
    return [
      { key: "review_id", label: "评论 ID" },
      { key: "rating", label: "评分" },
      { key: "text", label: "评论" },
      { key: "verified_purchase", label: "验证购买" },
      { key: "review_time", label: "时间" },
    ];
  }
  if (
    toolId === "tiktok_product_search" ||
    toolId === "tiktok_product_detail" ||
    toolId === "tiktok_video_products" ||
    toolId === "tiktok_creator_showcase"
  ) {
    return [
      { key: "product_id", label: "商品 ID" },
      { key: "title", label: "标题" },
      { key: "price_amount", label: "价格" },
      { key: "sale_count", label: "销量" },
      { key: "rating", label: "评分" },
      { key: "review_count", label: "评论数" },
      { key: "shop_name", label: "店铺" },
    ];
  }
  if (toolId === "tiktok_creator_commerce") {
    return [
      { key: "creator_id", label: "达人 ID" },
      { key: "unique_id", label: "账号" },
      { key: "follower_count", label: "粉丝" },
      { key: "gmv_amount", label: "GMV" },
      { key: "units_sold", label: "销量" },
    ];
  }
  return VIDEO_COLUMNS;
}

function readValue(record: Record<string, unknown>, key: string): unknown {
  return key.split(".").reduce<unknown>((value, part) => {
    if (value && typeof value === "object") {
      return (value as Record<string, unknown>)[part];
    }
    return undefined;
  }, record);
}

function formatValue(record: Record<string, unknown>, key: string): string {
  const value = readValue(record, key);
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function rowKey(record: Record<string, unknown>, index: number): string {
  const candidate =
    record.video_id ||
    record.comment_id ||
    record.uid ||
    record.entity_id ||
    record.unique_id;
  return candidate ? String(candidate) : `row-${index}`;
}

function statusTone(status?: string) {
  if (status === "success") {
    return "bg-[var(--success-soft)] text-[var(--state-success)]";
  }
  if (status === "partial_success") {
    return "bg-[var(--warning-soft)] text-[var(--state-warning)]";
  }
  if (status === "failed") {
    return "bg-[var(--danger-soft)] text-[var(--state-danger)]";
  }
  return "bg-[var(--surface-muted)] text-[var(--text-tertiary)]";
}

function RunLine({ run }: { run: TikTokToolRun }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--text-tertiary)]">
      <span className="font-mono text-[var(--text-secondary)]">
        {run.endpoint_type || "unknown"}
      </span>
      <span className={`rounded-full px-2 py-0.5 ${statusTone(run.status)}`}>
        {run.status || "unknown"}
      </span>
      <span>{run.records_count ?? 0} 条</span>
      {run.run_id ? <span className="font-mono">{run.run_id.slice(0, 8)}</span> : null}
      {run.error ? (
        <span className="text-[var(--state-danger)]">{run.error}</span>
      ) : null}
      {run.superseded_by ? (
        <span>已被 {run.superseded_by} 替代</span>
      ) : null}
    </div>
  );
}

export default function TikTokWorkbenchPage() {
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: fetchProjects,
  });
  const projects = projectsQuery.data ?? [];
  const [projectIdOverride, setProjectIdOverride] = useState("");
  const projectId = projectIdOverride || projects[0]?.id || "";
  const [tab, setTab] = useState<Tab>("trends");
  const [formError, setFormError] = useState<string | null>(null);

  const [trendCountry, setTrendCountry] = useState("US");
  const [trendPeriod, setTrendPeriod] = useState(7);
  const [trendLimit, setTrendLimit] = useState(50);

  const [videoMode, setVideoMode] = useState<VideoMode>("search");
  const [videoQuery, setVideoQuery] = useState("");
  const [videoHashtag, setVideoHashtag] = useState("");
  const [videoId, setVideoId] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [videoLimit, setVideoLimit] = useState(50);
  const [includeReplies, setIncludeReplies] = useState(true);

  const [creatorMode, setCreatorMode] = useState<CreatorMode>("profile");
  const [creatorHandle, setCreatorHandle] = useState("");
  const [creatorQuery, setCreatorQuery] = useState("");
  const [creatorLimit, setCreatorLimit] = useState(20);
  const [includeVideos, setIncludeVideos] = useState(true);
  const [includeFans, setIncludeFans] = useState(false);

  const [productMode, setProductMode] = useState<ProductMode>("search");
  const [productQuery, setProductQuery] = useState("");
  const [productId, setProductId] = useState("");
  const [productRegion, setProductRegion] = useState("US");
  const [productLimit, setProductLimit] = useState(20);
  const [productVideoId, setProductVideoId] = useState("");
  const [showcaseOffset, setShowcaseOffset] = useState(0);
  const [credentialModalOpen, setCredentialModalOpen] = useState(false);
  const [cookieInput, setCookieInput] = useState("");
  const [credentialError, setCredentialError] = useState<string | null>(null);
  const [savingCredential, setSavingCredential] = useState(false);
  const [lastRequest, setLastRequest] = useState<{
    toolId: string;
    params: Record<string, unknown>;
  } | null>(null);

  const mutation = useMutation({
    mutationFn: async ({
      toolId,
      params,
    }: {
      toolId: string;
      params: Record<string, unknown>;
    }) => {
      if (!projectId) throw new Error("请先选择项目");
      return runTikTokTool(toolId, projectId, params);
    },
    onSuccess: (data) => {
      const needsCredential = data.errors?.some((error) =>
        error.startsWith("credential_required:")
      );
      if (needsCredential) {
        setCredentialModalOpen(true);
      }
    },
  });

  const result: TikTokToolResult | undefined = mutation.data;
  const allRecords = result?.records ?? [];
  const columns = useMemo(() => columnsFor(result?.tool_id), [result?.tool_id]);
  const records = allRecords.slice(0, 100);
  const error =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error?.message;

  function buildRequest(): { toolId: string; params: Record<string, unknown> } | null {
    if (tab === "trends") {
      return {
        toolId: "tiktok_trend_rank",
        params: {
          country_code: trendCountry,
          period: trendPeriod,
          limit: trendLimit,
        },
      };
    }
    if (tab === "videos") {
      if (videoMode === "search") {
        return {
          toolId: "tiktok_video_search",
          params: { query: videoQuery.trim(), limit: videoLimit },
        };
      }
      if (videoMode === "hashtag") {
        return {
          toolId: "tiktok_hashtag_videos",
          params: { hashtag: videoHashtag.trim(), limit: videoLimit },
        };
      }
      if (videoMode === "detail") {
        return {
          toolId: "tiktok_video_detail",
          params: {
            video_id: videoId.trim(),
            video_url: videoUrl.trim() || undefined,
          },
        };
      }
      return {
        toolId: "tiktok_video_comments",
        params: {
          video_id: videoId.trim(),
          video_url: videoUrl.trim() || undefined,
          limit: videoLimit,
          include_replies: includeReplies,
        },
      };
    }
    if (tab === "products") {
      if (productMode === "search") {
        return {
          toolId: "tiktok_product_search",
          params: {
            query: productQuery.trim(),
            region: productRegion,
            limit: productLimit,
          },
        };
      }
      if (productMode === "detail") {
        return {
          toolId: "tiktok_product_detail",
          params: {
            product_id: productId.trim() || undefined,
            region: productRegion,
          },
        };
      }
      if (productMode === "video_products") {
        return {
          toolId: "tiktok_video_products",
          params: { video_id: productVideoId.trim() },
        };
      }
      if (productMode === "creator_showcase") {
        return {
          toolId: "tiktok_creator_showcase",
          params: { offset: showcaseOffset, limit: productLimit },
        };
      }
      return {
        toolId: "tiktok_product_reviews",
        params: {
          product_id: productId.trim(),
          region: productRegion,
          limit: productLimit,
        },
      };
    }
    if (creatorMode === "profile") {
      return {
        toolId: "tiktok_creator_profile",
        params: {
          handle: creatorHandle.trim().replace(/^@/, ""),
          include_videos: includeVideos,
          video_limit: creatorLimit,
          include_fans: includeFans,
        },
      };
    }
    return {
      toolId: "tiktok_creator_search",
      params: { query: creatorQuery.trim(), limit: creatorLimit },
    };
  }

  function runTool() {
    setFormError(null);
    const request = buildRequest();
    if (!request) return;
    if (request.toolId === "tiktok_video_search" && !request.params.query) {
      setFormError("请输入关键词");
      return;
    }
    if (request.toolId === "tiktok_hashtag_videos" && !request.params.hashtag) {
      setFormError("请输入话题名");
      return;
    }
    if (
      request.toolId === "tiktok_video_detail" &&
      !request.params.video_id &&
      !request.params.video_url
    ) {
      setFormError("请输入视频 ID 或视频 URL");
      return;
    }
    if (
      request.toolId === "tiktok_video_comments" &&
      !request.params.video_id &&
      !request.params.video_url
    ) {
      setFormError("请输入视频 ID 或视频 URL");
      return;
    }
    if (request.toolId === "tiktok_creator_profile" && !request.params.handle) {
      setFormError("请输入达人 handle");
      return;
    }
    if (request.toolId === "tiktok_creator_search" && !request.params.query) {
      setFormError("请输入搜索词");
      return;
    }
    if (request.toolId === "tiktok_product_search" && !request.params.query) {
      setFormError("请输入商品关键词");
      return;
    }
    if (
      (request.toolId === "tiktok_product_detail" ||
        request.toolId === "tiktok_product_reviews") &&
      !request.params.product_id
    ) {
      setFormError("请输入商品 ID");
      return;
    }
    if (
      request.toolId === "tiktok_video_products" &&
      !request.params.video_id
    ) {
      setFormError("请输入视频 ID");
      return;
    }
    setLastRequest(request);
    mutation.mutate(request);
  }

  async function saveCreatorCookie() {
    const cookie = cookieInput.trim();
    if (!cookie) {
      setCredentialError("请输入 TikTok 创作者 Cookie");
      return;
    }
    setCredentialError(null);
    setSavingCredential(true);
    try {
      await updateCredential("tiktok", { creator_cookie: cookie });
      setCredentialModalOpen(false);
      setCookieInput("");
      if (lastRequest) mutation.mutate(lastRequest);
    } catch (error) {
      setCredentialError(
        error instanceof ApiError ? error.message : String(error)
      );
    } finally {
      setSavingCredential(false);
    }
  }

  const activeTool = result?.tool_id ?? buildRequest()?.toolId ?? "—";

  return (
    <AppShell
      title="TikTok 工作台"
      description="内容、趋势与电商采集工具台"
      brief="按趋势、视频、达人、商品四个页签调用 TikTok 工具。每次运行返回记录、状态与上游 run。"
      breadcrumbs={[{ label: "工具" }, { label: "TikTok" }]}
    >
      <section className="flex flex-wrap items-end gap-3 rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] px-5 py-4">
        <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
          项目
          <select
            className="min-h-10 min-w-56 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm text-[var(--text-primary)]"
            value={projectId}
            onChange={(event) => setProjectIdOverride(event.target.value)}
            disabled={projectsQuery.isLoading}
          >
            {projects.length === 0 ? <option value="">暂无项目</option> : null}
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
        <div className="ml-auto flex flex-wrap items-center gap-2 text-xs text-[var(--text-tertiary)]">
          <span>当前工具</span>
          <span className="rounded bg-[var(--surface-muted)] px-2 py-1 font-mono text-[var(--text-secondary)]">
            {activeTool}
          </span>
          <button
            type="button"
            className="inline-flex min-h-10 items-center gap-2 rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-3 text-sm font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
            onClick={() => projectsQuery.refetch()}
            disabled={projectsQuery.isFetching}
          >
            <Search size={14} /> 刷新项目
          </button>
        </div>
      </section>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="TikTok 工作台页签">
        {[
          { id: "trends" as Tab, label: "趋势", icon: TrendingUp },
          { id: "videos" as Tab, label: "视频", icon: Play },
          { id: "creators" as Tab, label: "达人", icon: Users },
          { id: "products" as Tab, label: "商品", icon: Database },
        ].map((item) => {
          const Icon = item.icon;
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(item.id)}
              className={`inline-flex min-h-10 items-center gap-2 rounded-[var(--radius-2)] border px-4 text-sm font-semibold ${
                active
                  ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                  : "border-[var(--border-subtle)] bg-[var(--surface-primary)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              <Icon size={15} /> {item.label}
            </button>
          );
        })}
      </div>

      <section className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
        {tab === "trends" ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
              国家
              <select
                className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                value={trendCountry}
                onChange={(event) => setTrendCountry(event.target.value)}
              >
                {COUNTRIES.map((country) => (
                  <option key={country.value} value={country.value}>
                    {country.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
              周期
              <select
                className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                value={trendPeriod}
                onChange={(event) => setTrendPeriod(Number(event.target.value))}
              >
                {PERIODS.map((period) => (
                  <option key={period.value} value={period.value}>
                    {period.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
              条数
              <input
                type="number"
                min={1}
                max={200}
                className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                value={trendLimit}
                onChange={(event) => setTrendLimit(Number(event.target.value))}
              />
            </label>
          </div>
        ) : null}

        {tab === "videos" ? (
          <div className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              {[
                { id: "search" as VideoMode, label: "关键词搜索" },
                { id: "hashtag" as VideoMode, label: "话题视频" },
                { id: "detail" as VideoMode, label: "视频详情" },
                { id: "comments" as VideoMode, label: "评论" },
              ].map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => setVideoMode(mode.id)}
                  className={`min-h-9 rounded-[var(--radius-2)] border px-3 text-xs font-semibold ${
                    videoMode === mode.id
                      ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                      : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {videoMode === "search" ? (
                <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                  关键词
                  <input
                    className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                    value={videoQuery}
                    onChange={(event) => setVideoQuery(event.target.value)}
                    placeholder="breast pump"
                  />
                </label>
              ) : null}
              {videoMode === "hashtag" ? (
                <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                  话题（不含 #）
                  <input
                    className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                    value={videoHashtag}
                    onChange={(event) => setVideoHashtag(event.target.value)}
                    placeholder="newbornmusthaves"
                  />
                </label>
              ) : null}
              {videoMode === "detail" || videoMode === "comments" ? (
                <>
                  <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                    视频 ID
                    <input
                      className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                      value={videoId}
                      onChange={(event) => setVideoId(event.target.value)}
                      placeholder="7534061113365859586"
                    />
                  </label>
                  <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                    或视频 URL
                    <input
                      className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                      value={videoUrl}
                      onChange={(event) => setVideoUrl(event.target.value)}
                      placeholder="https://www.tiktok.com/@user/video/..."
                    />
                  </label>
                </>
              ) : null}
              <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                条数
                <input
                  type="number"
                  min={1}
                  max={200}
                  className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                  value={videoLimit}
                  onChange={(event) => setVideoLimit(Number(event.target.value))}
                />
              </label>
              {videoMode === "comments" ? (
                <label className="flex min-h-10 items-center gap-2 text-xs font-semibold text-[var(--text-secondary)]">
                  <input
                    type="checkbox"
                    checked={includeReplies}
                    onChange={(event) => setIncludeReplies(event.target.checked)}
                  />
                  同时拉取回复
                </label>
              ) : null}
            </div>
          </div>
        ) : null}

        {tab === "creators" ? (
          <div className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              {[
                { id: "profile" as CreatorMode, label: "达人资料" },
                { id: "search" as CreatorMode, label: "达人搜索" },
              ].map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => setCreatorMode(mode.id)}
                  className={`min-h-9 rounded-[var(--radius-2)] border px-3 text-xs font-semibold ${
                    creatorMode === mode.id
                      ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                      : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {creatorMode === "profile" ? (
                <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                  达人 handle
                  <input
                    className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                    value={creatorHandle}
                    onChange={(event) => setCreatorHandle(event.target.value)}
                    placeholder="momcozy"
                  />
                </label>
              ) : (
                <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                  搜索词
                  <input
                    className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                    value={creatorQuery}
                    onChange={(event) => setCreatorQuery(event.target.value)}
                    placeholder="breast pump review"
                  />
                </label>
              )}
              <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                条数
                <input
                  type="number"
                  min={1}
                  max={200}
                  className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                  value={creatorLimit}
                  onChange={(event) => setCreatorLimit(Number(event.target.value))}
                />
              </label>
              {creatorMode === "profile" ? (
                <div className="flex flex-wrap gap-4 text-xs font-semibold text-[var(--text-secondary)]">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={includeVideos}
                      onChange={(event) => setIncludeVideos(event.target.checked)}
                    />
                    拉取作品
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={includeFans}
                      onChange={(event) => setIncludeFans(event.target.checked)}
                    />
                    拉取粉丝
                  </label>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}

        {tab === "products" ? (
          <div className="grid gap-4">
            <div className="flex flex-wrap gap-2">
              {[
                { id: "search" as ProductMode, label: "商品搜索" },
                { id: "detail" as ProductMode, label: "商品详情" },
                { id: "reviews" as ProductMode, label: "商品评论" },
                { id: "video_products" as ProductMode, label: "视频关联商品" },
                { id: "creator_showcase" as ProductMode, label: "达人橱窗" },
              ].map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => setProductMode(mode.id)}
                  className={`min-h-9 rounded-[var(--radius-2)] border px-3 text-xs font-semibold ${
                    productMode === mode.id
                      ? "border-[var(--action-primary)] bg-[var(--accent-1-soft)] text-[var(--action-primary)]"
                      : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {productMode === "search" ? (
                <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                  关键词
                  <input
                    className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                    value={productQuery}
                    onChange={(event) => setProductQuery(event.target.value)}
                    placeholder="breast pump"
                  />
                </label>
              ) : productMode === "video_products" ? (
                <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                  视频 ID
                  <input
                    className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                    value={productVideoId}
                    onChange={(event) => setProductVideoId(event.target.value)}
                    placeholder="7670318941658483981"
                  />
                </label>
              ) : productMode === "creator_showcase" ? (
                <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                  偏移量
                  <input
                    type="number"
                    min={0}
                    className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                    value={showcaseOffset}
                    onChange={(event) => setShowcaseOffset(Number(event.target.value))}
                  />
                </label>
              ) : (
                <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                  商品 ID
                  <input
                    className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                    value={productId}
                    onChange={(event) => setProductId(event.target.value)}
                    placeholder="1732417183133045688"
                  />
                </label>
              )}
              <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                市场
                <select
                  className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                  value={productRegion}
                  onChange={(event) => setProductRegion(event.target.value)}
                >
                  {COUNTRIES.map((country) => (
                    <option key={country.value} value={country.value}>
                      {country.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
                条数
                <input
                  type="number"
                  min={1}
                  max={100}
                  className="min-h-10 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 text-sm"
                  value={productLimit}
                  onChange={(event) => setProductLimit(Number(event.target.value))}
                />
              </label>
            </div>
            <p className="text-xs text-[var(--text-tertiary)]">
              商品搜索优先走 Apify，失败后回退 TikHub。美国商品发现使用 TikHub V2。
            </p>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={runTool}
            disabled={mutation.isPending || !projectId}
            className="inline-flex min-h-10 items-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 text-sm font-semibold text-[var(--text-inverse)] hover:bg-[var(--action-primary-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Play size={15} />
            )}
            {mutation.isPending ? "运行中" : "运行工具"}
          </button>
          <span className="text-xs text-[var(--text-tertiary)]">
            结果最多展示 100 条；完整记录写入数据集。
          </span>
        </div>
      </section>

      {formError || error ? (
        <div className="flex items-start gap-3 rounded-[var(--radius-2)] border border-[var(--danger-1)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--state-danger)]">
          <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
          <p>{formError || error}</p>
        </div>
      ) : null}

      {result ? (
        <section className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <StatTile label="记录数" value={String(result.records_count)} hint={result.tool_id} />
            <StatTile label="上游调用" value={String(result.runs.length)} hint="run 数" />
            <StatTile label="错误" value={String(result.errors.length)} hint="errors" />
          </div>

          <div className="rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusTone(result.status)}`}>
                {result.status}
              </span>
              <span className="font-mono text-xs text-[var(--text-secondary)]">
                {result.tool_id}
              </span>
              <span className="text-xs text-[var(--text-tertiary)]">
                {result.records_count} 条
              </span>
            </div>
            <div className="grid gap-1.5">
              {result.runs.map((run, index) => (
                <RunLine key={`${run.endpoint_type}-${index}`} run={run} />
              ))}
            </div>
          </div>

          <div className="overflow-hidden rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)]">
            <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border-subtle)] px-5 py-3">
              {columns.map((column) => (
                <span
                  key={column.key}
                  className="rounded bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-semibold text-[var(--text-tertiary)]"
                >
                  {column.label}
                </span>
              ))}
            </div>
            {records.length === 0 ? (
              <div className="grid place-items-center gap-2 px-5 py-12 text-center">
                <FileText size={28} className="text-[var(--text-tertiary)]" />
                <p className="text-sm font-semibold text-[var(--text-secondary)]">没有记录</p>
                <p className="text-xs text-[var(--text-tertiary)]">
                  查看上游 run 状态，或换一个关键词/账号再试。
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[64rem] border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] text-[var(--text-tertiary)]">
                      {columns.map((column) => (
                        <th key={column.key} className="px-4 py-2.5 font-semibold">
                          {column.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {records.map((record, index) => (
                      <tr
                        key={rowKey(record, index)}
                        className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--surface-muted)]"
                      >
                        {columns.map((column) => (
                          <td
                            key={column.key}
                            className="max-w-[28rem] truncate px-4 py-2.5 text-[var(--text-secondary)]"
                            title={formatValue(record, column.key)}
                          >
                            {formatValue(record, column.key)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <details className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-4 py-3 text-xs text-[var(--text-secondary)]">
            <summary className="cursor-pointer font-semibold">查看原始 JSON（前 5 条）</summary>
            <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px]">
              {JSON.stringify(allRecords.slice(0, 5), null, 2)}
            </pre>
          </details>
        </section>
      ) : null}

      {credentialModalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="tiktok-cookie-title"
        >
          <div className="w-full max-w-lg rounded-[var(--radius-3)] border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-5 shadow-xl">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2">
                <KeyRound size={18} className="text-[var(--action-primary)]" />
                <h2
                  id="tiktok-cookie-title"
                  className="text-base font-semibold text-[var(--text-primary)]"
                >
                  连接 TikTok 创作者账号
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setCredentialModalOpen(false)}
                className="rounded p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                aria-label="关闭"
              >
                <X size={16} />
              </button>
            </div>
            <p className="mt-2 text-sm text-[var(--text-secondary)]">
              商品关系接口需要已登录 TikTok 网页版的 Cookie。Cookie 只保存在本工作区的加密凭证库，不会显示在运行记录中。
            </p>
            <label className="mt-4 grid gap-1 text-xs font-semibold text-[var(--text-secondary)]">
              Cookie
              <textarea
                value={cookieInput}
                onChange={(event) => setCookieInput(event.target.value)}
                rows={5}
                placeholder="sessionid=...; ttwid=...;"
                className="w-full rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2 font-mono text-xs text-[var(--text-primary)]"
              />
            </label>
            <p className="mt-2 text-xs text-[var(--text-tertiary)]">
              获取方法：登录 TikTok 网页版，打开开发者工具，复制任意请求的 Cookie 请求头。
            </p>
            {credentialError ? (
              <p className="mt-2 text-sm text-[var(--state-danger)]">{credentialError}</p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCredentialModalOpen(false)}
                className="rounded-[var(--radius-2)] border border-[var(--border-subtle)] px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              >
                取消
              </button>
              <button
                type="button"
                onClick={saveCreatorCookie}
                disabled={savingCredential}
                className="inline-flex items-center gap-2 rounded-[var(--radius-2)] bg-[var(--action-primary)] px-4 py-2 text-sm font-semibold text-[var(--text-inverse)] disabled:opacity-60"
              >
                {savingCredential ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <KeyRound size={14} />
                )}
                保存并继续
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
