# API Market Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `API市场` frontend page that presents overseas social API capabilities as a marketplace-style catalog with searchable cards, platform/category filters, endpoint drill-down, and fixture-only private-deployment readiness gates.

**Architecture:** Build a frontend-first marketplace surface from the existing overseas social provider catalog and mock/fixture contracts. The first implementation uses local static catalog data and existing Workbench UI primitives; it does not call TikHub hosted endpoints, platform APIs, credentials, LLM providers, or production write APIs. The page mirrors TikHub marketplace information architecture: marketplace list -> endpoint detail -> request/parameter view -> fixture/test gate -> response/schema review, adapted to Data Intelligence Hub compliance boundaries.

**Tech Stack:** Next.js App Router, React, TypeScript, Vitest, Playwright, lucide-react, existing `AppShell`, `WorkbenchPanel`, `WorkbenchFact`, and `WorkbenchTag`.

---

## Evidence And Boundary Notes

- TikHub public dashboard shell confirms the route `/dashboard/api-marketplace`; bundle routing confirms a detail route `/dashboard/api-marketplace/:encodedPath`.
- TikHub marketplace chunk string evidence shows list filters: platform, category, interface type, free credit, discount, tag, search, pagination.
- TikHub card evidence shows platform badge, method, endpoint path, description, cost, free-credit support, discount support, and tag.
- TikHub endpoint detail chunk evidence shows parameters, request body, API key check, test endpoint, response table/json toggle, copy/download, and AI response assist.
- Data Intelligence Hub adaptation must replace live “test endpoint” with `fixture-only preview` and `adapter plan gate`.
- Default boundary stays: `provider_call=false`, `provider_call_attempted=false`, `credential_read_attempted=false`, `live_client_created=false`, `production unchanged`.

## Product Shape

### Route

- List page: `/api-market`
- Detail page: `/api-market/[endpointId]`
- Sidebar label: `API市场`
- Sidebar group: `工程中心`, above `自动采集`

### Marketplace List

The page should feel like a functional market/catalog, not a landing page:

- Header: `API市场`
- Search: by platform, provider id, endpoint path, resource group, policy flag, official doc URL.
- Filters:
  - Platform: All, YouTube, Reddit, X, Instagram, Threads, TikTok Research, LinkedIn.
  - Category/resource group: content search, post search, comments, creator/profile, media/feed, mentions, insights, research.
  - Priority: P0, P1, P2, P3.
  - Stability: high, medium, low.
  - Execution mode: fixture ready, adapter planned, live gated.
- Stats:
  - `7` overseas platforms.
  - endpoint count from local catalog.
  - `provider_call=false`.
  - live-gated count.
- Card fields:
  - platform icon/name
  - method-like tag: `GET`, `POST`, or `READ`
  - endpoint path
  - resource group/category
  - provider id
  - official API viability
  - cost/quota hint
  - stability/priority
  - compliance flags
  - `查看详情` link
  - `生成预案` deep link to `/automation?platform=<platform>&endpoint=<endpoint>`

### Endpoint Detail

Detail page should be the internal equivalent of TikHub’s endpoint detail page, but with private-deployment gates:

- Breadcrumb: `API市场 / <platform> / <endpoint>`
- Overview:
  - endpoint path
  - provider id
  - data domain
  - SDK selection
  - official docs
- Request Contract:
  - method
  - parameters
  - request body fixture example
  - auth mode
  - required credentials shown as labels only
- Private Deployment Gate:
  - readiness status
  - dependency status
  - adapter module
  - fixture replay support
  - blocked actions
  - forbidden live actions
- Data Contract:
  - raw schema
  - normalized schema
  - dataset preview target
  - evidence reference requirement
- Fixture Response Preview:
  - table view
  - JSON view
  - copy fixture JSON button
  - download should not be added in MVP to avoid extra file-output side effects.
- Actions:
  - `返回市场`
  - `生成 fixture 预案`
  - no live `Test Endpoint` button in MVP.

## File Structure

- Create: `apps/web/src/types/api-market.ts`
  - Endpoint catalog UI types and filter types.
- Create: `apps/web/src/lib/api-market-catalog.ts`
  - Static MVP catalog built from the first-batch overseas social providers.
  - Pure functions for filtering, slug lookup, detail lookup, and stats.
- Create: `apps/web/src/components/api-market/api-market-workspace.tsx`
  - Client component for list page search/filter/card grid.
- Create: `apps/web/src/components/api-market/api-market-detail-workspace.tsx`
  - Client component for endpoint detail, request contract, gate, and fixture response preview.
- Create: `apps/web/src/app/api-market/page.tsx`
  - AppShell wrapper for list page.
- Create: `apps/web/src/app/api-market/[endpointId]/page.tsx`
  - AppShell wrapper for detail page, with `notFound()` for unknown ids.
- Modify: `apps/web/src/components/layout/sidebar.tsx`
  - Add `API市场` nav item under `engineItems`.
- Create: `apps/web/tests/unit/api-market.test.ts`
  - Catalog/filter/detail tests.
- Modify: `apps/web/tests/e2e/main-flows.spec.ts`
  - Route smoke for `/api-market` and a detail page.

## Task 1: Catalog Types And Data

**Files:**
- Create: `apps/web/src/types/api-market.ts`
- Create: `apps/web/src/lib/api-market-catalog.ts`
- Create: `apps/web/tests/unit/api-market.test.ts`

- [ ] **Step 1: Write failing unit tests**

Add `apps/web/tests/unit/api-market.test.ts`:

```ts
import {
  apiMarketEndpoints,
  buildApiMarketStats,
  findApiMarketEndpointById,
  filterApiMarketEndpoints,
} from "@/lib/api-market-catalog";

describe("api market catalog", () => {
  it("contains overseas social API marketplace endpoints with no live side effects", () => {
    expect(apiMarketEndpoints.length).toBeGreaterThanOrEqual(14);
    expect(apiMarketEndpoints.every((item) => item.providerCall === false)).toBe(true);
    expect(apiMarketEndpoints.every((item) => item.liveClientCreated === false)).toBe(true);
    expect(apiMarketEndpoints.every((item) => item.productionWriteAllowed === false)).toBe(true);
  });

  it("filters by platform, category, and text query", () => {
    const results = filterApiMarketEndpoints({
      platform: "youtube",
      category: "comment_threads",
      query: "commentThreads",
      priority: "all",
      stability: "all",
      executionMode: "all",
    });

    expect(results.map((item) => item.endpoint)).toContain("commentThreads.list");
    expect(results.every((item) => item.platform === "youtube")).toBe(true);
  });

  it("finds endpoint details by stable id", () => {
    const endpoint = findApiMarketEndpointById("youtube-v3-videos-list");
    expect(endpoint?.providerId).toBe("youtube.v3");
    expect(endpoint?.endpoint).toBe("videos.list");
    expect(endpoint?.request.parameters.some((param) => param.name === "part")).toBe(true);
  });

  it("builds marketplace stats from the catalog", () => {
    const stats = buildApiMarketStats(apiMarketEndpoints);
    expect(stats.platformCount).toBe(7);
    expect(stats.providerCallAttempted).toBe(false);
    expect(stats.liveGatedCount).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run test to verify red state**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/api-market.test.ts
```

Expected: fail because `@/lib/api-market-catalog` does not exist.

- [ ] **Step 3: Create catalog types**

Create `apps/web/src/types/api-market.ts`:

```ts
export type ApiMarketPlatform =
  | "youtube"
  | "reddit"
  | "x"
  | "instagram"
  | "threads"
  | "tiktok"
  | "linkedin";

export type ApiMarketCategory =
  | "content_search"
  | "video_detail"
  | "comment_threads"
  | "post_search"
  | "post_lookup"
  | "creator_profile"
  | "media_feed"
  | "mentions"
  | "insights"
  | "research"
  | "organization_updates";

export type ApiMarketPriority = "p0" | "p1" | "p2" | "p3";
export type ApiMarketStability = "high" | "medium" | "low";
export type ApiMarketExecutionMode = "fixture_ready" | "adapter_planned" | "live_gated";

export type ApiMarketParameter = {
  name: string;
  in: "query" | "path" | "body";
  type: "string" | "number" | "boolean" | "array" | "object";
  required: boolean;
  description: string;
  example?: string;
};

export type ApiMarketEndpoint = {
  id: string;
  platform: ApiMarketPlatform;
  platformLabel: string;
  providerId: string;
  method: "GET" | "POST" | "READ";
  endpoint: string;
  title: string;
  summary: string;
  category: ApiMarketCategory;
  dataDomain: string[];
  authMode: string;
  apiVersion: string;
  officialDocs: string[];
  sdkPackage: string;
  sdkStatus: "selected" | "candidate" | "manual_review";
  stability: ApiMarketStability;
  priority: ApiMarketPriority;
  executionMode: ApiMarketExecutionMode;
  quotaHint: string;
  costHint: string;
  policyFlags: string[];
  blockedActions: string[];
  requiredCredentials: string[];
  providerCall: false;
  providerCallAttempted: false;
  credentialReadAttempted: false;
  liveClientCreated: false;
  productionWriteAllowed: false;
  request: {
    parameters: ApiMarketParameter[];
    requestBodyExample?: Record<string, unknown>;
  };
  responsePreview: {
    schemaVersion: string;
    sample: Record<string, unknown>;
  };
};

export type ApiMarketFilterState = {
  platform: ApiMarketPlatform | "all";
  category: ApiMarketCategory | "all";
  query: string;
  priority: ApiMarketPriority | "all";
  stability: ApiMarketStability | "all";
  executionMode: ApiMarketExecutionMode | "all";
};

export type ApiMarketStats = {
  platformCount: number;
  endpointCount: number;
  p0Count: number;
  fixtureReadyCount: number;
  liveGatedCount: number;
  providerCallAttempted: false;
};
```

- [ ] **Step 4: Create static MVP catalog and helpers**

Create `apps/web/src/lib/api-market-catalog.ts` with at least these endpoints:

```ts
import type {
  ApiMarketEndpoint,
  ApiMarketFilterState,
  ApiMarketStats,
} from "@/types/api-market";

export const apiMarketEndpoints: ApiMarketEndpoint[] = [
  {
    id: "youtube-v3-search-list",
    platform: "youtube",
    platformLabel: "YouTube",
    providerId: "youtube.v3",
    method: "GET",
    endpoint: "search.list",
    title: "YouTube Search",
    summary: "Search public YouTube videos/channels/playlists through the official Data API.",
    category: "content_search",
    dataDomain: ["content_search"],
    authMode: "Google OAuth2 / API Key",
    apiVersion: "v3",
    officialDocs: ["https://developers.google.com/youtube/v3/docs/search/list"],
    sdkPackage: "google-api-python-client",
    sdkStatus: "selected",
    stability: "high",
    priority: "p0",
    executionMode: "fixture_ready",
    quotaHint: "YouTube Data API quota units; search is cost-sensitive.",
    costHint: "official quota",
    policyFlags: ["official_api", "no_ai_training_from_raw_source_without_governance"],
    blockedActions: ["login_cookie_capture", "unauthorized_video_download"],
    requiredCredentials: ["api_key"],
    providerCall: false,
    providerCallAttempted: false,
    credentialReadAttempted: false,
    liveClientCreated: false,
    productionWriteAllowed: false,
    request: {
      parameters: [
        { name: "part", in: "query", type: "string", required: true, description: "Resource part selector.", example: "snippet" },
        { name: "q", in: "query", type: "string", required: true, description: "Search query.", example: "social listening" },
        { name: "maxResults", in: "query", type: "number", required: false, description: "Small approved page size.", example: "5" },
      ],
    },
    responsePreview: {
      schemaVersion: "social_raw.v1",
      sample: {
        raw_record_id: "fixture:youtube.v3:search.list:1",
        provider_id: "youtube.v3",
        provider_call: false,
        evidence_ref: "fixture://youtube/search.list/1",
      },
    },
  },
  {
    id: "youtube-v3-videos-list",
    platform: "youtube",
    platformLabel: "YouTube",
    providerId: "youtube.v3",
    method: "GET",
    endpoint: "videos.list",
    title: "YouTube Video Detail",
    summary: "Read official public video metadata for reviewed video ids.",
    category: "video_detail",
    dataDomain: ["video_detail"],
    authMode: "Google OAuth2 / API Key",
    apiVersion: "v3",
    officialDocs: ["https://developers.google.com/youtube/v3/docs/videos/list"],
    sdkPackage: "google-api-python-client",
    sdkStatus: "selected",
    stability: "high",
    priority: "p0",
    executionMode: "fixture_ready",
    quotaHint: "YouTube Data API quota units.",
    costHint: "official quota",
    policyFlags: ["official_api"],
    blockedActions: ["unauthorized_video_download"],
    requiredCredentials: ["api_key"],
    providerCall: false,
    providerCallAttempted: false,
    credentialReadAttempted: false,
    liveClientCreated: false,
    productionWriteAllowed: false,
    request: {
      parameters: [
        { name: "part", in: "query", type: "string", required: true, description: "Requested video fields.", example: "snippet,statistics" },
        { name: "id", in: "query", type: "string", required: true, description: "Comma-separated video ids.", example: "video_id" },
      ],
    },
    responsePreview: {
      schemaVersion: "social_post.v1",
      sample: {
        item_id: "social_post:youtube.v3:1",
        provider_id: "youtube.v3",
        author_policy: "hashed",
        evidence_ref: "fixture://youtube/videos.list/1",
      },
    },
  },
  {
    id: "youtube-v3-commentthreads-list",
    platform: "youtube",
    platformLabel: "YouTube",
    providerId: "youtube.v3",
    method: "GET",
    endpoint: "commentThreads.list",
    title: "YouTube Comment Threads",
    summary: "Read public comment thread fixtures and prepare official comment collection gates.",
    category: "comment_threads",
    dataDomain: ["comment_threads"],
    authMode: "Google OAuth2 / API Key",
    apiVersion: "v3",
    officialDocs: ["https://developers.google.com/youtube/v3/docs/commentThreads/list"],
    sdkPackage: "google-api-python-client",
    sdkStatus: "selected",
    stability: "high",
    priority: "p0",
    executionMode: "fixture_ready",
    quotaHint: "YouTube Data API quota units.",
    costHint: "official quota",
    policyFlags: ["official_api", "comment_author_policy_hashed"],
    blockedActions: ["user_profile_deep_merge"],
    requiredCredentials: ["api_key"],
    providerCall: false,
    providerCallAttempted: false,
    credentialReadAttempted: false,
    liveClientCreated: false,
    productionWriteAllowed: false,
    request: {
      parameters: [
        { name: "part", in: "query", type: "string", required: true, description: "Requested comment fields.", example: "snippet,replies" },
        { name: "videoId", in: "query", type: "string", required: true, description: "Video id.", example: "video_id" },
      ],
    },
    responsePreview: {
      schemaVersion: "social_comment.v1",
      sample: {
        item_id: "social_comment:youtube.v3:1",
        provider_id: "youtube.v3",
        author_policy: "hashed",
        evidence_ref: "fixture://youtube/commentThreads.list/1",
      },
    },
  },
  {
    id: "reddit-praw-search",
    platform: "reddit",
    platformLabel: "Reddit",
    providerId: "reddit.praw",
    method: "GET",
    endpoint: "search",
    title: "Reddit Search",
    summary: "Search authorized Reddit public/community content through OAuth-scoped access.",
    category: "post_search",
    dataDomain: ["post_search"],
    authMode: "OAuth2 Bearer + User-Agent + App credentials",
    apiVersion: "OAuth2",
    officialDocs: ["https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki"],
    sdkPackage: "asyncpraw",
    sdkStatus: "selected",
    stability: "medium",
    priority: "p1",
    executionMode: "adapter_planned",
    quotaHint: "Default OAuth client rate limit profile; policy gate required.",
    costHint: "contract-sensitive",
    policyFlags: ["no_ai_training", "compliance_contract_required"],
    blockedActions: ["private_data_scrape", "login_state_capture", "captcha_bypass"],
    requiredCredentials: ["oauth_token", "client_id", "client_secret"],
    providerCall: false,
    providerCallAttempted: false,
    credentialReadAttempted: false,
    liveClientCreated: false,
    productionWriteAllowed: false,
    request: {
      parameters: [
        { name: "q", in: "query", type: "string", required: true, description: "Search query.", example: "brand keyword" },
        { name: "subreddit", in: "query", type: "string", required: false, description: "Optional subreddit scope.", example: "skincareaddiction" },
      ],
    },
    responsePreview: {
      schemaVersion: "social_voc_item.v1",
      sample: {
        item_id: "social_voc_item:reddit.praw:1",
        provider_id: "reddit.praw",
        provider_call: false,
        evidence_ref: "fixture://reddit/search/1",
      },
    },
  },
];

const extraEndpoints: ApiMarketEndpoint[] = [
  cloneEndpoint("reddit-praw-comments-new", "reddit", "Reddit", "reddit.praw", "comments.new", "comment_threads", "Reddit Comments"),
  cloneEndpoint("x-v2-tweets-search-recent", "x", "X", "x.v2", "tweets/search/recent", "post_search", "X Recent Search"),
  cloneEndpoint("x-v2-tweets", "x", "X", "x.v2", "tweets", "post_lookup", "X Tweet Lookup"),
  cloneEndpoint("instagram-graph-media", "instagram", "Instagram", "instagram_graph.v19", "media", "media_feed", "Instagram Media"),
  cloneEndpoint("instagram-graph-mentions", "instagram", "Instagram", "instagram_graph.v19", "mentions", "mentions", "Instagram Mentions"),
  cloneEndpoint("threads-graph-threads", "threads", "Threads", "threads.graph.v1", "threads", "media_feed", "Threads Feed"),
  cloneEndpoint("threads-graph-replies", "threads", "Threads", "threads.graph.v1", "replies", "comment_threads", "Threads Replies"),
  cloneEndpoint("tiktok-research-video-search", "tiktok", "TikTok Research", "tiktok_research", "video.search", "research", "TikTok Research Video Search"),
  cloneEndpoint("tiktok-research-comment-list", "tiktok", "TikTok Research", "tiktok_research", "comment.list", "comment_threads", "TikTok Research Comments"),
  cloneEndpoint("linkedin-mcdm-ugcposts", "linkedin", "LinkedIn", "linkedin.mcdm", "ugcPosts", "organization_updates", "LinkedIn UGC Posts"),
  cloneEndpoint("linkedin-mcdm-socialactions", "linkedin", "LinkedIn", "linkedin.mcdm", "socialActions", "organization_updates", "LinkedIn Social Actions"),
];

apiMarketEndpoints.push(...extraEndpoints);

function cloneEndpoint(
  id: ApiMarketEndpoint["id"],
  platform: ApiMarketEndpoint["platform"],
  platformLabel: string,
  providerId: string,
  endpoint: string,
  category: ApiMarketEndpoint["category"],
  title: string,
): ApiMarketEndpoint {
  return {
    ...apiMarketEndpoints[0],
    id,
    platform,
    platformLabel,
    providerId,
    endpoint,
    title,
    summary: `${title} fixture-only marketplace contract for private deployment planning.`,
    category,
    dataDomain: [category],
    stability: platform === "youtube" ? "high" : platform === "tiktok" || platform === "threads" ? "low" : "medium",
    priority: platform === "youtube" ? "p0" : platform === "reddit" ? "p1" : "p2",
    executionMode: platform === "youtube" ? "fixture_ready" : "adapter_planned",
    sdkPackage: platform === "reddit" ? "asyncpraw" : platform === "youtube" ? "google-api-python-client" : "official_or_http_client_manual_review",
    requiredCredentials: platform === "youtube" ? ["api_key"] : ["access_token_or_oauth_app"],
    officialDocs: [],
    request: {
      parameters: [
        { name: "scope", in: "query", type: "string", required: true, description: "Authorized query or owned asset scope.", example: "reviewed_keyword" },
        { name: "limit", in: "query", type: "number", required: false, description: "Small fixture replay limit.", example: "5" },
      ],
    },
    responsePreview: {
      schemaVersion: "social_raw.v1",
      sample: {
        raw_record_id: `fixture:${providerId}:${endpoint}:1`,
        provider_id: providerId,
        provider_call: false,
        evidence_ref: `fixture://${platform}/${endpoint}/1`,
      },
    },
  };
}

export function findApiMarketEndpointById(id: string): ApiMarketEndpoint | null {
  return apiMarketEndpoints.find((endpoint) => endpoint.id === id) ?? null;
}

export function filterApiMarketEndpoints(filters: ApiMarketFilterState): ApiMarketEndpoint[] {
  const query = filters.query.trim().toLowerCase();
  return apiMarketEndpoints.filter((endpoint) => {
    if (filters.platform !== "all" && endpoint.platform !== filters.platform) return false;
    if (filters.category !== "all" && endpoint.category !== filters.category) return false;
    if (filters.priority !== "all" && endpoint.priority !== filters.priority) return false;
    if (filters.stability !== "all" && endpoint.stability !== filters.stability) return false;
    if (filters.executionMode !== "all" && endpoint.executionMode !== filters.executionMode) return false;
    if (!query) return true;
    const haystack = [
      endpoint.platformLabel,
      endpoint.providerId,
      endpoint.endpoint,
      endpoint.title,
      endpoint.summary,
      endpoint.category,
      ...endpoint.policyFlags,
      ...endpoint.blockedActions,
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

export function buildApiMarketStats(endpoints: ApiMarketEndpoint[]): ApiMarketStats {
  return {
    endpointCount: endpoints.length,
    fixtureReadyCount: endpoints.filter((endpoint) => endpoint.executionMode === "fixture_ready").length,
    liveGatedCount: endpoints.filter((endpoint) => endpoint.executionMode !== "fixture_ready").length,
    p0Count: endpoints.filter((endpoint) => endpoint.priority === "p0").length,
    platformCount: new Set(endpoints.map((endpoint) => endpoint.platform)).size,
    providerCallAttempted: false,
  };
}
```

- [ ] **Step 5: Run unit tests green**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/api-market.test.ts
```

Expected: pass.

## Task 2: API Market List Page

**Files:**
- Create: `apps/web/src/app/api-market/page.tsx`
- Create: `apps/web/src/components/api-market/api-market-workspace.tsx`
- Modify: `apps/web/src/components/layout/sidebar.tsx`

- [ ] **Step 1: Create route shell**

Create `apps/web/src/app/api-market/page.tsx`:

```tsx
import { ApiMarketWorkspace } from "@/components/api-market/api-market-workspace";
import { AppShell } from "@/components/layout/app-shell";

export default function ApiMarketPage() {
  return (
    <AppShell
      title="API市场"
      description="官方/授权 API 能力、私有化部署入口和 fixture-only 预案"
      brief="API市场把海外社媒官方 API、授权边界、SDK 选型、成本/限流和数据合同放在同一页复核；默认只做 fixture 预案，不读取凭据、不调用平台、不写生产。"
      signals={["官方 API 优先", "私有化部署", "fixture-only", "合规边界"]}
    >
      <ApiMarketWorkspace />
    </AppShell>
  );
}
```

- [ ] **Step 2: Implement marketplace workspace**

Create `apps/web/src/components/api-market/api-market-workspace.tsx`:

```tsx
"use client";

import { ArrowUpRight, DatabaseZap, Filter, Search, ShieldCheck, Store, Zap } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import {
  apiMarketEndpoints,
  buildApiMarketStats,
  filterApiMarketEndpoints,
} from "@/lib/api-market-catalog";
import type {
  ApiMarketCategory,
  ApiMarketExecutionMode,
  ApiMarketFilterState,
  ApiMarketPlatform,
  ApiMarketPriority,
  ApiMarketStability,
} from "@/types/api-market";
import { WorkbenchFact, WorkbenchPanel, WorkbenchTag } from "@/components/common/workbench-ui";

const platforms: Array<ApiMarketPlatform | "all"> = ["all", "youtube", "reddit", "x", "instagram", "threads", "tiktok", "linkedin"];
const categories: Array<ApiMarketCategory | "all"> = ["all", "content_search", "video_detail", "comment_threads", "post_search", "post_lookup", "creator_profile", "media_feed", "mentions", "insights", "research", "organization_updates"];
const priorities: Array<ApiMarketPriority | "all"> = ["all", "p0", "p1", "p2", "p3"];
const stabilities: Array<ApiMarketStability | "all"> = ["all", "high", "medium", "low"];
const executionModes: Array<ApiMarketExecutionMode | "all"> = ["all", "fixture_ready", "adapter_planned", "live_gated"];

export function ApiMarketWorkspace() {
  const [filters, setFilters] = useState<ApiMarketFilterState>({
    category: "all",
    executionMode: "all",
    platform: "all",
    priority: "all",
    query: "",
    stability: "all",
  });

  const endpoints = useMemo(() => filterApiMarketEndpoints(filters), [filters]);
  const stats = useMemo(() => buildApiMarketStats(apiMarketEndpoints), []);

  function patchFilters(next: Partial<ApiMarketFilterState>) {
    setFilters((current) => ({ ...current, ...next }));
  }

  return (
    <div className="grid min-w-0 gap-5">
      <WorkbenchPanel
        icon={Store}
        label="API Market"
        title="海外社媒 API 私有化市场"
        subtitle="Marketplace-style endpoint catalog with no provider call by default"
        action={<WorkbenchTag tone="neutral">provider_call=false</WorkbenchTag>}
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <WorkbenchFact label="platforms" value={String(stats.platformCount)} />
          <WorkbenchFact label="endpoints" value={String(stats.endpointCount)} />
          <WorkbenchFact label="p0_official" value={String(stats.p0Count)} />
          <WorkbenchFact label="fixture_ready" value={String(stats.fixtureReadyCount)} />
          <WorkbenchFact label="live_gated" value={String(stats.liveGatedCount)} />
        </div>
      </WorkbenchPanel>

      <section className="grid min-w-0 gap-3 rounded-2xl border border-[#E8D4CB] bg-white/85 p-4">
        <label className="grid min-w-0 gap-2 text-sm font-semibold text-[#3B2924]">
          <span className="inline-flex items-center gap-2">
            <Search size={15} aria-hidden="true" />
            搜索 API、平台、endpoint 或 policy flag
          </span>
          <input
            className="h-11 w-full min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm outline-none transition focus:border-[#C96F5C] focus:ring-4 focus:ring-[#F3D7CE]"
            onChange={(event) => patchFilters({ query: event.target.value })}
            placeholder="videos.list / Reddit / comments / no_ai_training"
            value={filters.query}
          />
        </label>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <SelectFilter label="平台" value={filters.platform} options={platforms} onChange={(value) => patchFilters({ platform: value as ApiMarketFilterState["platform"] })} />
          <SelectFilter label="分类" value={filters.category} options={categories} onChange={(value) => patchFilters({ category: value as ApiMarketFilterState["category"] })} />
          <SelectFilter label="优先级" value={filters.priority} options={priorities} onChange={(value) => patchFilters({ priority: value as ApiMarketFilterState["priority"] })} />
          <SelectFilter label="稳定性" value={filters.stability} options={stabilities} onChange={(value) => patchFilters({ stability: value as ApiMarketFilterState["stability"] })} />
          <SelectFilter label="执行状态" value={filters.executionMode} options={executionModes} onChange={(value) => patchFilters({ executionMode: value as ApiMarketFilterState["executionMode"] })} />
        </div>
      </section>

      <section className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {endpoints.map((endpoint) => (
          <article className="grid min-w-0 gap-3 rounded-2xl border border-[#E8D4CB] bg-[#FFFDFC] p-4" key={endpoint.id}>
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase text-[#B47767]">{endpoint.platformLabel}</p>
                <h2 className="mt-1 break-words text-base font-semibold text-[#2E201C]">{endpoint.title}</h2>
              </div>
              <WorkbenchTag tone={endpoint.priority === "p0" ? "green" : "amber"}>{endpoint.priority}</WorkbenchTag>
            </div>
            <p className="break-all rounded-xl bg-white px-3 py-2 text-sm font-semibold text-[#3B2924]">
              {endpoint.method} / {endpoint.endpoint}
            </p>
            <p className="text-sm leading-6 text-[#7A625A]">{endpoint.summary}</p>
            <div className="flex flex-wrap gap-2">
              <WorkbenchTag tone="muted">{endpoint.category}</WorkbenchTag>
              <WorkbenchTag tone={endpoint.stability === "high" ? "green" : endpoint.stability === "medium" ? "amber" : "rose"}>{endpoint.stability}</WorkbenchTag>
              <WorkbenchTag tone="neutral">{endpoint.executionMode}</WorkbenchTag>
            </div>
            <div className="grid gap-2 text-xs text-[#7A625A]">
              <span className="inline-flex items-center gap-2"><DatabaseZap size={14} aria-hidden="true" />{endpoint.sdkPackage}</span>
              <span className="inline-flex items-center gap-2"><ShieldCheck size={14} aria-hidden="true" />{endpoint.policyFlags.slice(0, 2).join(" / ")}</span>
              <span className="inline-flex items-center gap-2"><Zap size={14} aria-hidden="true" />{endpoint.costHint}</span>
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              <Link className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white" href={`/api-market/${endpoint.id}`}>
                查看详情
                <ArrowUpRight size={15} aria-hidden="true" />
              </Link>
              <Link className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7A625A]" href={`/automation?platform=${endpoint.platform}&endpoint=${encodeURIComponent(endpoint.endpoint)}`}>
                生成预案
              </Link>
            </div>
          </article>
        ))}
      </section>

      {endpoints.length === 0 ? (
        <section className="rounded-2xl border border-[#E8D4CB] bg-white p-6 text-center text-sm font-semibold text-[#7A625A]">
          没有找到匹配的 API endpoint。
        </section>
      ) : null}
    </div>
  );
}

function SelectFilter({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  options: readonly string[];
  value: string;
}) {
  return (
    <label className="grid min-w-0 gap-2 text-xs font-semibold uppercase text-[#B47767]">
      <span className="inline-flex items-center gap-2">
        <Filter size={13} aria-hidden="true" />
        {label}
      </span>
      <select
        className="h-10 w-full min-w-0 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm normal-case text-[#3B2924] outline-none"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === "all" ? "全部" : option}
          </option>
        ))}
      </select>
    </label>
  );
}
```

- [ ] **Step 3: Add sidebar nav item**

Modify `apps/web/src/components/layout/sidebar.tsx`:

```tsx
import {
  // existing icons...
  Store,
} from "lucide-react";
```

Then update `engineItems`:

```tsx
const engineItems = [
  { href: route("/api-market"), label: "API市场", icon: Store },
  { href: route("/automation"), label: "自动采集", icon: Bot },
  { href: route("/datasets"), label: "数据集", icon: TableProperties },
  { href: route("/tasks"), label: "采集任务", icon: SquareStack },
  { href: route("/sources"), label: "数据源", icon: Boxes },
  { href: route("/raw-records"), label: "原始数据", icon: Database },
  { href: route("/entities"), label: "实体库", icon: Megaphone },
] satisfies NavItem[];
```

- [ ] **Step 4: Run route-level type and lint checks**

Run:

```bash
corepack pnpm lint:web
corepack pnpm --dir apps/web build
```

Expected: pass.

## Task 3: Endpoint Detail Page

**Files:**
- Create: `apps/web/src/app/api-market/[endpointId]/page.tsx`
- Create: `apps/web/src/components/api-market/api-market-detail-workspace.tsx`
- Modify: `apps/web/tests/unit/api-market.test.ts`

- [ ] **Step 1: Add detail lookup assertions**

Append to `apps/web/tests/unit/api-market.test.ts`:

```ts
it("returns null for unknown endpoint id", () => {
  expect(findApiMarketEndpointById("missing-endpoint")).toBeNull();
});
```

- [ ] **Step 2: Create detail route**

Create `apps/web/src/app/api-market/[endpointId]/page.tsx`:

```tsx
import { notFound } from "next/navigation";

import { ApiMarketDetailWorkspace } from "@/components/api-market/api-market-detail-workspace";
import { AppShell } from "@/components/layout/app-shell";
import { findApiMarketEndpointById } from "@/lib/api-market-catalog";

export default async function ApiMarketDetailPage({
  params,
}: {
  params: Promise<{ endpointId: string }>;
}) {
  const { endpointId } = await params;
  const endpoint = findApiMarketEndpointById(endpointId);

  if (!endpoint) {
    notFound();
  }

  return (
    <AppShell
      title="API市场"
      description={`${endpoint.platformLabel} / ${endpoint.endpoint}`}
      brief="Endpoint 详情页只展示私有化部署所需的请求合同、数据合同、adapter gate 和 fixture 响应；MVP 不提供 live test。"
      signals={["Endpoint 合同", "Adapter Gate", "Fixture 响应", "no provider call"]}
    >
      <ApiMarketDetailWorkspace endpoint={endpoint} />
    </AppShell>
  );
}
```

- [ ] **Step 3: Create detail workspace**

Create `apps/web/src/components/api-market/api-market-detail-workspace.tsx`:

```tsx
"use client";

import { ArrowLeft, Clipboard, Code2, FileJson2, LockKeyhole, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { WorkbenchFact, WorkbenchPanel, WorkbenchTag } from "@/components/common/workbench-ui";
import type { ApiMarketEndpoint } from "@/types/api-market";

export function ApiMarketDetailWorkspace({ endpoint }: { endpoint: ApiMarketEndpoint }) {
  const [responseMode, setResponseMode] = useState<"table" | "json">("table");
  const responseJson = useMemo(() => JSON.stringify(endpoint.responsePreview.sample, null, 2), [endpoint]);
  const parameterRows = endpoint.request.parameters;

  async function copyFixture() {
    await navigator.clipboard.writeText(responseJson);
  }

  return (
    <div className="grid min-w-0 gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-[#E8D4CB] bg-white px-3 text-sm font-semibold text-[#7A625A]" href="/api-market">
          <ArrowLeft size={15} aria-hidden="true" />
          返回市场
        </Link>
        <WorkbenchTag tone="neutral">provider_call=false</WorkbenchTag>
      </div>

      <WorkbenchPanel icon={Code2} label="Endpoint" title={endpoint.title} subtitle={endpoint.summary}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <WorkbenchFact label="platform" value={endpoint.platformLabel} />
          <WorkbenchFact label="provider_id" value={endpoint.providerId} />
          <WorkbenchFact label="endpoint" value={endpoint.endpoint} />
          <WorkbenchFact label="api_version" value={endpoint.apiVersion} />
          <WorkbenchFact label="sdk_package" value={endpoint.sdkPackage} />
          <WorkbenchFact label="sdk_status" value={endpoint.sdkStatus} />
          <WorkbenchFact label="stability" value={endpoint.stability} />
          <WorkbenchFact label="priority" value={endpoint.priority} />
        </div>
      </WorkbenchPanel>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <WorkbenchPanel icon={FileJson2} label="Request Contract" title="请求合同与参数">
          <div className="grid min-w-0 gap-2">
            {parameterRows.map((parameter) => (
              <div className="grid min-w-0 gap-2 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] p-3 sm:grid-cols-[160px_90px_90px_minmax(0,1fr)]" key={parameter.name}>
                <p className="break-all text-sm font-semibold text-[#2E201C]">{parameter.name}</p>
                <p className="text-sm text-[#7A625A]">{parameter.in}</p>
                <p className="text-sm text-[#7A625A]">{parameter.type}</p>
                <p className="break-words text-sm text-[#7A625A]">
                  {parameter.required ? "required: " : "optional: "}
                  {parameter.description}
                </p>
              </div>
            ))}
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel icon={LockKeyhole} label="Private Gate" title="私有化部署边界">
          <div className="grid gap-2">
            <WorkbenchFact label="provider_call_attempted" value={String(endpoint.providerCallAttempted)} />
            <WorkbenchFact label="credential_read_attempted" value={String(endpoint.credentialReadAttempted)} />
            <WorkbenchFact label="live_client_created" value={String(endpoint.liveClientCreated)} />
            <WorkbenchFact label="production_write_allowed" value={String(endpoint.productionWriteAllowed)} />
          </div>
        </WorkbenchPanel>
      </section>

      <WorkbenchPanel
        icon={ShieldCheck}
        label="Fixture Response"
        title="Fixture 响应预览"
        action={
          <button className="inline-flex min-h-9 items-center gap-2 rounded-xl bg-[#C96F5C] px-3 text-sm font-semibold text-white" onClick={copyFixture} type="button">
            <Clipboard size={14} aria-hidden="true" />
            复制 JSON
          </button>
        }
      >
        <div className="mb-3 flex flex-wrap gap-2">
          <button className="rounded-xl border border-[#E8D4CB] bg-white px-3 py-2 text-sm font-semibold text-[#7A625A]" onClick={() => setResponseMode("table")} type="button">表格</button>
          <button className="rounded-xl border border-[#E8D4CB] bg-white px-3 py-2 text-sm font-semibold text-[#7A625A]" onClick={() => setResponseMode("json")} type="button">JSON</button>
        </div>
        {responseMode === "json" ? (
          <pre className="max-h-96 overflow-auto rounded-xl bg-[#1D1D1F] p-4 text-xs leading-6 text-white">{responseJson}</pre>
        ) : (
          <div className="grid min-w-0 gap-2">
            {Object.entries(endpoint.responsePreview.sample).map(([key, value]) => (
              <div className="grid min-w-0 gap-2 rounded-xl border border-[#F0E1D9] bg-[#FFFDFC] px-3 py-2 sm:grid-cols-[180px_minmax(0,1fr)]" key={key}>
                <span className="break-all text-xs font-semibold uppercase text-[#B47767]">{key}</span>
                <span className="break-all text-sm font-semibold text-[#2E201C]">{String(value)}</span>
              </div>
            ))}
          </div>
        )}
      </WorkbenchPanel>
    </div>
  );
}
```

- [ ] **Step 4: Run focused unit and build checks**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/unit/api-market.test.ts
corepack pnpm lint:web
corepack pnpm --dir apps/web build
```

Expected: pass.

## Task 4: E2E And Visual Smoke

**Files:**
- Modify: `apps/web/tests/e2e/main-flows.spec.ts`

- [ ] **Step 1: Add E2E route smoke**

Add a test near existing route smoke tests:

```ts
test("renders API market list and endpoint detail without live calls", async ({ page }) => {
  await page.goto("/api-market");
  await expect(page.getByRole("heading", { name: "API市场" })).toBeVisible();
  await expect(page.getByText("provider_call=false")).toBeVisible();
  await expect(page.getByText("YouTube Search")).toBeVisible();

  await page.getByRole("link", { name: "查看详情" }).first().click();
  await expect(page.getByText("请求合同与参数")).toBeVisible();
  await expect(page.getByText("provider_call_attempted")).toBeVisible();
  await expect(page.getByText("Fixture 响应预览")).toBeVisible();
});
```

If Playwright strict mode rejects duplicate `查看详情`, scope the link to the `YouTube Search` card:

```ts
const youtubeCard = page.getByText("YouTube Search").locator("..").locator("..");
await youtubeCard.getByRole("link", { name: "查看详情" }).click();
```

- [ ] **Step 2: Run E2E in mock mode**

Run:

```bash
corepack pnpm --dir apps/web exec playwright test --grep "API market"
```

Expected: pass.

- [ ] **Step 3: Run manual browser smoke for desktop and mobile**

Run Next dev:

```bash
NEXT_PUBLIC_MOCK_API=true corepack pnpm --dir apps/web exec next dev --hostname 127.0.0.1 --port 3105
```

Then use Playwright to verify:

```bash
corepack pnpm --dir apps/web exec node - <<'NODE'
const { chromium } = require('@playwright/test');

async function run(viewport) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('http://127.0.0.1:3105/api-market', { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: 'API市场' }).waitFor();
  await page.getByText('YouTube Search').waitFor();
  const overflow = await page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth));
  await browser.close();
  return { overflow, errors };
}

(async () => {
  const desktop = await run({ width: 1440, height: 1000 });
  const mobile = await run({ width: 390, height: 900 });
  console.log(JSON.stringify({ desktop, mobile }, null, 2));
  if (desktop.overflow || mobile.overflow || desktop.errors.length || mobile.errors.length) process.exit(1);
})();
NODE
```

Expected: desktop/mobile overflow is `0`; console error arrays are empty.

## Task 5: Final Validation And Commit

**Files:**
- Commit only files from this plan.

- [ ] **Step 1: Run full web verification**

Run:

```bash
corepack pnpm lint:web
corepack pnpm test:web
corepack pnpm --dir apps/web build
git diff --check
```

Expected: pass. Existing Next workspace-root warning is acceptable if unchanged.

- [ ] **Step 2: Credential field scan**

Run:

```bash
rg -n "(?i)(api[_-]?key|secret|token|password|private[_-]?key|bearer|sk-[A-Za-z0-9])" \
  apps/web/src/types/api-market.ts \
  apps/web/src/lib/api-market-catalog.ts \
  apps/web/src/components/api-market \
  apps/web/src/app/api-market \
  apps/web/src/components/layout/sidebar.tsx \
  apps/web/tests/unit/api-market.test.ts \
  apps/web/tests/e2e/main-flows.spec.ts
```

Expected: only credential field labels such as `api_key` or `bearer`; no actual secrets.

- [ ] **Step 3: Stage exact files**

Run:

```bash
git add -- \
  apps/web/src/types/api-market.ts \
  apps/web/src/lib/api-market-catalog.ts \
  apps/web/src/components/api-market/api-market-workspace.tsx \
  apps/web/src/components/api-market/api-market-detail-workspace.tsx \
  apps/web/src/app/api-market/page.tsx \
  apps/web/src/app/api-market/[endpointId]/page.tsx \
  apps/web/src/components/layout/sidebar.tsx \
  apps/web/tests/unit/api-market.test.ts \
  apps/web/tests/e2e/main-flows.spec.ts \
  docs/superpowers/plans/2026-07-10-api-market-page.md
```

- [ ] **Step 4: Commit and push**

Run:

```bash
git commit -m "feat: add API market page"
git push
gh pr checks 11 --watch=false
```

Expected: report local validation and PR check state separately.

## Acceptance Criteria

- `/api-market` renders in the existing Data Intelligence Hub style, not as a separate marketing landing page.
- `/api-market` has search, platform filter, category filter, priority filter, stability filter, and execution-mode filter.
- Endpoint cards show platform, endpoint, method, SDK, policy flags, cost/quota hint, stability, priority, and no-provider-call boundary.
- `/api-market/[endpointId]` renders request contract, private deployment gate, data/fixture response preview, and copy JSON action.
- No live provider test button exists in MVP.
- No API keys, tokens, cookies, or credentials are read, rendered, or submitted.
- `provider_call=false`, `credential_read_attempted=false`, `live_client_created=false`, and `production_write_allowed=false` are visible.
- Desktop and 390px mobile have no horizontal overflow.
- Local lint/test/build pass; PR checks are observed after push.
