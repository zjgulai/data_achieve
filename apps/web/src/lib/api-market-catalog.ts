import type {
  ApiMarketEndpoint,
  ApiMarketFilterState,
  ApiMarketPlatform,
  ApiMarketPriority,
  ApiMarketSdkStatus,
  ApiMarketStability,
  ApiMarketStats,
} from "@/types/api-market";

type ProfileDefaultField =
  | "apiVersion"
  | "authMode"
  | "blockedActions"
  | "costHint"
  | "officialDocs"
  | "platformLabel"
  | "policyFlags"
  | "priority"
  | "providerId"
  | "quotaHint"
  | "requiredCredentials"
  | "sdkPackage"
  | "sdkStatus"
  | "stability";

type EndpointInput = Omit<
  ApiMarketEndpoint,
  | ProfileDefaultField
  | "credentialReadAttempted"
  | "liveClientCreated"
  | "productionWriteAllowed"
  | "providerCall"
  | "providerCallAttempted"
> &
  Partial<Pick<ApiMarketEndpoint, ProfileDefaultField>>;

const platformProfiles: Record<
  ApiMarketPlatform,
  {
    apiVersion: string;
    authMode: string;
    blockedActions: string[];
    costHint: string;
    officialDocs: string[];
    platformLabel: string;
    policyFlags: string[];
    priority: ApiMarketPriority;
    providerId: string;
    quotaHint: string;
    requiredCredentials: string[];
    sdkPackage: string;
    sdkStatus: ApiMarketSdkStatus;
    stability: ApiMarketStability;
  }
> = {
  instagram: {
    apiVersion: "v19",
    authMode: "Meta App Token + Page/Business token + permissions",
    blockedActions: ["consumer_dm_capture", "private_profile_deep_scrape", "login_state_collection"],
    costHint: "app review and owned asset scope",
    officialDocs: ["https://developers.facebook.com/docs/instagram-api"],
    platformLabel: "Instagram",
    policyFlags: ["business_account_required", "page_level_authorization", "no_ai_training"],
    priority: "p2",
    providerId: "instagram_graph.v19",
    quotaHint: "Meta Graph rate limits vary by app and asset.",
    requiredCredentials: ["access_token", "app_secret", "page_access_token"],
    sdkPackage: "facebook-business",
    sdkStatus: "candidate",
    stability: "medium",
  },
  linkedin: {
    apiVersion: "v2",
    authMode: "LinkedIn MDP/MCM OAuth + app tier",
    blockedActions: ["private_message", "contact_graph_expansion", "member_profile_broad_scan"],
    costHint: "tier review required",
    officialDocs: ["https://developer.linkedin.com/product-catalog"],
    platformLabel: "LinkedIn",
    policyFlags: ["official_api_only", "version_tier_review_required", "no_ai_training"],
    priority: "p3",
    providerId: "linkedin.mcdm",
    quotaHint: "Member/company permissions and product tier define limits.",
    requiredCredentials: ["client_id", "client_secret", "access_token"],
    sdkPackage: "linkedin-api-client",
    sdkStatus: "manual_review",
    stability: "medium",
  },
  reddit: {
    apiVersion: "OAuth2",
    authMode: "OAuth2 Bearer + User-Agent + App credentials",
    blockedActions: ["private_data_scrape", "login_state_capture", "captcha_bypass"],
    costHint: "contract-sensitive",
    officialDocs: ["https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki"],
    platformLabel: "Reddit",
    policyFlags: ["no_ai_training", "compliance_contract_required"],
    priority: "p1",
    providerId: "reddit.praw",
    quotaHint: "Default OAuth client rate limit profile; policy gate required.",
    requiredCredentials: ["oauth_token", "client_id", "client_secret"],
    sdkPackage: "asyncpraw",
    sdkStatus: "selected",
    stability: "medium",
  },
  threads: {
    apiVersion: "threads",
    authMode: "Meta threads scope + app review",
    blockedActions: ["login_state_capture", "private_account_enumeration"],
    costHint: "app review and owned asset scope",
    officialDocs: ["https://developers.facebook.com/docs/threads"],
    platformLabel: "Threads",
    policyFlags: ["strict_permissions_required", "no_ai_training"],
    priority: "p3",
    providerId: "threads.graph.v1",
    quotaHint: "Meta Graph/Threads limits vary by app and permission.",
    requiredCredentials: ["app_id", "app_secret", "access_token", "scope"],
    sdkPackage: "httpx",
    sdkStatus: "selected",
    stability: "low",
  },
  tiktok: {
    apiVersion: "research",
    authMode: "OAuth2 Bearer + VCE qualification",
    blockedActions: ["private_message", "login_state_capture", "captcha_bypass"],
    costHint: "research authorization required",
    officialDocs: ["https://developers.tiktok.com/doc/research-api-get-started"],
    platformLabel: "TikTok Research",
    policyFlags: ["research_only", "no_ai_training"],
    priority: "p3",
    providerId: "tiktok_research",
    quotaHint: "Research API request and record limits require approval.",
    requiredCredentials: ["access_token", "app_id", "app_secret"],
    sdkPackage: "TikTokResearchApi",
    sdkStatus: "manual_review",
    stability: "low",
  },
  x: {
    apiVersion: "v2",
    authMode: "OAuth2 Bearer / Paid product key",
    blockedActions: ["private_message", "dm", "login_cookie_capture"],
    costHint: "paid tier and max_cost_usd gate",
    officialDocs: ["https://docs.x.com/x-api/introduction"],
    platformLabel: "X",
    policyFlags: ["commercial_use_requires_paywall_terms", "no_ai_training"],
    priority: "p2",
    providerId: "x.v2",
    quotaHint: "Endpoint-specific limits and pay-per-use cost gate.",
    requiredCredentials: ["bearer_token", "app_id", "app_secret"],
    sdkPackage: "tweepy[async]",
    sdkStatus: "candidate",
    stability: "medium",
  },
  youtube: {
    apiVersion: "v3",
    authMode: "Google OAuth2 / API Key",
    blockedActions: ["login_cookie_capture", "unauthorized_video_download"],
    costHint: "official quota",
    officialDocs: ["https://developers.google.com/youtube/v3/docs"],
    platformLabel: "YouTube",
    policyFlags: ["official_api", "no_ai_training_from_raw_source_without_governance"],
    priority: "p0",
    providerId: "youtube.v3",
    quotaHint: "YouTube Data API quota units; search is cost-sensitive.",
    requiredCredentials: ["api_key"],
    sdkPackage: "google-api-python-client",
    sdkStatus: "selected",
    stability: "high",
  },
};

export const apiMarketEndpoints: ApiMarketEndpoint[] = [
  endpoint({
    category: "content_search",
    dataDomain: ["content_search"],
    endpoint: "search.list",
    executionMode: "fixture_ready",
    id: "youtube-v3-search-list",
    method: "GET",
    platform: "youtube",
    request: {
      parameters: [
        parameter("part", "query", "string", true, "Resource part selector.", "snippet"),
        parameter("q", "query", "string", true, "Search query.", "social listening"),
        parameter("maxResults", "query", "number", false, "Small approved page size.", "5"),
      ],
    },
    responsePreview: rawSample("youtube.v3", "search.list", "social_raw.v1"),
    summary: "Search public YouTube videos, channels, and playlists through the official Data API.",
    title: "YouTube Search",
  }),
  endpoint({
    category: "video_detail",
    dataDomain: ["video_detail"],
    endpoint: "videos.list",
    executionMode: "fixture_ready",
    id: "youtube-v3-videos-list",
    method: "GET",
    platform: "youtube",
    request: {
      parameters: [
        parameter("part", "query", "string", true, "Requested video fields.", "snippet,statistics"),
        parameter("id", "query", "string", true, "Comma-separated video ids.", "video_id"),
      ],
    },
    responsePreview: itemSample("youtube.v3", "videos.list", "social_post.v1"),
    summary: "Read official public video metadata for reviewed video ids.",
    title: "YouTube Video Detail",
  }),
  endpoint({
    category: "creator_profile",
    dataDomain: ["creator_profile"],
    endpoint: "channels.list",
    executionMode: "fixture_ready",
    id: "youtube-v3-channels-list",
    method: "GET",
    platform: "youtube",
    request: {
      parameters: [
        parameter("part", "query", "string", true, "Requested channel fields.", "snippet,statistics"),
        parameter("id", "query", "string", true, "Channel id.", "channel_id"),
      ],
    },
    responsePreview: itemSample("youtube.v3", "channels.list", "social_creator_snapshot.v1"),
    summary: "Read public channel metadata and creator snapshots from approved channel ids.",
    title: "YouTube Channel Snapshot",
  }),
  endpoint({
    category: "comment_threads",
    dataDomain: ["comment_threads"],
    endpoint: "commentThreads.list",
    executionMode: "fixture_ready",
    id: "youtube-v3-commentthreads-list",
    method: "GET",
    platform: "youtube",
    request: {
      parameters: [
        parameter("part", "query", "string", true, "Requested comment fields.", "snippet,replies"),
        parameter("videoId", "query", "string", true, "Video id.", "video_id"),
      ],
    },
    responsePreview: itemSample("youtube.v3", "commentThreads.list", "social_comment.v1"),
    summary: "Read public comment thread fixtures and prepare official comment collection gates.",
    title: "YouTube Comment Threads",
  }),
  endpoint({
    category: "post_search",
    dataDomain: ["post_search"],
    endpoint: "search",
    executionMode: "adapter_planned",
    id: "reddit-praw-search",
    method: "GET",
    platform: "reddit",
    request: {
      parameters: [
        parameter("q", "query", "string", true, "Search query.", "brand keyword"),
        parameter("subreddit", "query", "string", false, "Optional subreddit scope.", "skincareaddiction"),
      ],
    },
    responsePreview: itemSample("reddit.praw", "search", "social_voc_item.v1"),
    summary: "Search authorized Reddit public/community content through OAuth-scoped access.",
    title: "Reddit Search",
  }),
  endpoint({
    category: "post_search",
    dataDomain: ["post_search"],
    endpoint: "hot.list",
    executionMode: "adapter_planned",
    id: "reddit-praw-hot-list",
    method: "GET",
    platform: "reddit",
    request: {
      parameters: [
        parameter("subreddit", "query", "string", true, "Authorized subreddit scope.", "skincareaddiction"),
        parameter("limit", "query", "number", false, "Small fixture replay limit.", "5"),
      ],
    },
    responsePreview: itemSample("reddit.praw", "hot.list", "social_post.v1"),
    summary: "Review hot subreddit post collection through authorized OAuth boundaries.",
    title: "Reddit Hot Posts",
  }),
  endpoint({
    category: "comment_threads",
    dataDomain: ["comment_threads"],
    endpoint: "comments.new",
    executionMode: "adapter_planned",
    id: "reddit-praw-comments-new",
    method: "GET",
    platform: "reddit",
    request: {
      parameters: [
        parameter("subreddit", "query", "string", true, "Authorized subreddit scope.", "skincareaddiction"),
        parameter("limit", "query", "number", false, "Small fixture replay limit.", "5"),
      ],
    },
    responsePreview: itemSample("reddit.praw", "comments.new", "social_comment.v1"),
    summary: "Prepare read-only public comment review with no AI training or private data capture.",
    title: "Reddit New Comments",
  }),
  endpoint({
    category: "post_search",
    dataDomain: ["post_search"],
    endpoint: "tweets/search/recent",
    executionMode: "live_gated",
    id: "x-v2-tweets-search-recent",
    method: "GET",
    platform: "x",
    request: {
      parameters: [
        parameter("query", "query", "string", true, "Recent search query.", "brand keyword lang:en"),
        parameter("max_results", "query", "number", false, "Small approved page size.", "10"),
      ],
    },
    responsePreview: itemSample("x.v2", "tweets/search/recent", "social_post.v1"),
    summary: "Plan paid-tier recent search with cost budget and endpoint-specific rate gates.",
    title: "X Recent Search",
  }),
  endpoint({
    category: "post_lookup",
    dataDomain: ["post_lookup"],
    endpoint: "tweets",
    executionMode: "live_gated",
    id: "x-v2-tweets",
    method: "GET",
    platform: "x",
    request: {
      parameters: [
        parameter("ids", "query", "array", true, "Reviewed tweet ids.", "tweet_id"),
        parameter("tweet.fields", "query", "string", false, "Requested fields.", "created_at,public_metrics"),
      ],
    },
    responsePreview: itemSample("x.v2", "tweets", "social_post.v1"),
    summary: "Lookup reviewed X posts after paid access and budget approval.",
    title: "X Tweet Lookup",
  }),
  endpoint({
    category: "media_feed",
    dataDomain: ["media_feed"],
    endpoint: "media",
    executionMode: "live_gated",
    id: "instagram-graph-media",
    method: "GET",
    platform: "instagram",
    request: {
      parameters: [
        parameter("ig_user_id", "path", "string", true, "Owned or authorized Instagram business account id.", "17841400000000000"),
        parameter("fields", "query", "string", false, "Requested fields.", "id,caption,media_type,timestamp"),
      ],
    },
    responsePreview: itemSample("instagram_graph.v19", "media", "social_post.v1"),
    summary: "Review authorized business/creator media access through Meta Graph permissions.",
    title: "Instagram Media",
  }),
  endpoint({
    category: "mentions",
    dataDomain: ["mentions"],
    endpoint: "mentions",
    executionMode: "live_gated",
    id: "instagram-graph-mentions",
    method: "GET",
    platform: "instagram",
    request: {
      parameters: [
        parameter("ig_user_id", "path", "string", true, "Owned or authorized Instagram business account id.", "17841400000000000"),
        parameter("fields", "query", "string", false, "Mention fields.", "caption,media_type,permalink"),
      ],
    },
    responsePreview: itemSample("instagram_graph.v19", "mentions", "social_voc_item.v1"),
    summary: "Plan limited mention monitoring for approved business assets only.",
    title: "Instagram Mentions",
  }),
  endpoint({
    category: "insights",
    dataDomain: ["insights"],
    endpoint: "insights",
    executionMode: "live_gated",
    id: "instagram-graph-insights",
    method: "GET",
    platform: "instagram",
    request: {
      parameters: [
        parameter("media_id", "path", "string", true, "Owned media id.", "media_id"),
        parameter("metric", "query", "string", true, "Approved insight metric.", "impressions,reach"),
      ],
    },
    responsePreview: itemSample("instagram_graph.v19", "insights", "social_topic_trend.v1"),
    summary: "Plan owned-asset insight collection after Meta app review.",
    title: "Instagram Insights",
  }),
  endpoint({
    category: "media_feed",
    dataDomain: ["media_feed"],
    endpoint: "threads",
    executionMode: "live_gated",
    id: "threads-graph-threads",
    method: "GET",
    platform: "threads",
    request: {
      parameters: [
        parameter("user_id", "path", "string", true, "Authorized Threads profile id.", "threads_user_id"),
        parameter("fields", "query", "string", false, "Requested fields.", "id,text,timestamp"),
      ],
    },
    responsePreview: itemSample("threads.graph.v1", "threads", "social_post.v1"),
    summary: "Plan authorized Threads content reads through Meta app permissions.",
    title: "Threads Feed",
  }),
  endpoint({
    category: "comment_threads",
    dataDomain: ["comment_threads"],
    endpoint: "replies",
    executionMode: "live_gated",
    id: "threads-graph-replies",
    method: "GET",
    platform: "threads",
    request: {
      parameters: [
        parameter("thread_id", "path", "string", true, "Reviewed thread id.", "thread_id"),
        parameter("limit", "query", "number", false, "Small approved page size.", "5"),
      ],
    },
    responsePreview: itemSample("threads.graph.v1", "replies", "social_comment.v1"),
    summary: "Prepare reply review for authorized Threads assets only.",
    title: "Threads Replies",
  }),
  endpoint({
    category: "research",
    dataDomain: ["research", "video_snapshot"],
    endpoint: "video.search",
    executionMode: "live_gated",
    id: "tiktok-research-video-search",
    method: "POST",
    platform: "tiktok",
    request: {
      parameters: [parameter("query", "body", "object", true, "Research API query object.", "keyword condition")],
      requestBodyExample: {
        query: { and: [{ operation: "EQ", field_name: "region_code", field_values: ["US"] }] },
        max_count: 10,
      },
    },
    responsePreview: itemSample("tiktok_research", "video.search", "social_post.v1"),
    summary: "Plan research-only TikTok video search after qualification and VCE gates.",
    title: "TikTok Research Video Search",
  }),
  endpoint({
    category: "comment_threads",
    dataDomain: ["video_comment"],
    endpoint: "comment.list",
    executionMode: "live_gated",
    id: "tiktok-research-comment-list",
    method: "GET",
    platform: "tiktok",
    request: {
      parameters: [
        parameter("video_id", "query", "string", true, "Reviewed video id.", "video_id"),
        parameter("max_count", "query", "number", false, "Small approved page size.", "10"),
      ],
    },
    responsePreview: itemSample("tiktok_research", "comment.list", "social_comment.v1"),
    summary: "Plan research-only public comment review after qualification approval.",
    title: "TikTok Research Comments",
  }),
  endpoint({
    category: "organization_updates",
    dataDomain: ["company_updates", "ugc_posts"],
    endpoint: "ugcPosts",
    executionMode: "live_gated",
    id: "linkedin-mcdm-ugcposts",
    method: "GET",
    platform: "linkedin",
    request: {
      parameters: [
        parameter("organization", "query", "string", true, "Authorized organization URN.", "urn:li:organization:123"),
        parameter("count", "query", "number", false, "Small approved page size.", "10"),
      ],
    },
    responsePreview: itemSample("linkedin.mcdm", "ugcPosts", "social_post.v1"),
    summary: "Prepare LinkedIn organization post review after product/tier approval.",
    title: "LinkedIn UGC Posts",
  }),
  endpoint({
    category: "organization_updates",
    dataDomain: ["social_actions"],
    endpoint: "socialActions",
    executionMode: "live_gated",
    id: "linkedin-mcdm-socialactions",
    method: "GET",
    platform: "linkedin",
    request: {
      parameters: [
        parameter("activity", "query", "string", true, "Reviewed activity URN.", "urn:li:activity:123"),
        parameter("projection", "query", "string", false, "Approved projection.", "(comments,likes)"),
      ],
    },
    responsePreview: itemSample("linkedin.mcdm", "socialActions", "social_comment.v1"),
    summary: "Prepare LinkedIn social action reads with no contact graph expansion.",
    title: "LinkedIn Social Actions",
  }),
];

export function findApiMarketEndpointById(id: string): ApiMarketEndpoint | null {
  return apiMarketEndpoints.find((endpointItem) => endpointItem.id === id) ?? null;
}

export function filterApiMarketEndpoints(filters: ApiMarketFilterState): ApiMarketEndpoint[] {
  const query = filters.query.trim().toLowerCase();
  return apiMarketEndpoints.filter((endpointItem) => {
    if (filters.platform !== "all" && endpointItem.platform !== filters.platform) {
      return false;
    }
    if (filters.category !== "all" && endpointItem.category !== filters.category) {
      return false;
    }
    if (filters.priority !== "all" && endpointItem.priority !== filters.priority) {
      return false;
    }
    if (filters.stability !== "all" && endpointItem.stability !== filters.stability) {
      return false;
    }
    if (filters.executionMode !== "all" && endpointItem.executionMode !== filters.executionMode) {
      return false;
    }
    if (!query) {
      return true;
    }

    return [
      endpointItem.platformLabel,
      endpointItem.providerId,
      endpointItem.endpoint,
      endpointItem.title,
      endpointItem.summary,
      endpointItem.category,
      endpointItem.authMode,
      endpointItem.sdkPackage,
      ...endpointItem.officialDocs,
      ...endpointItem.policyFlags,
      ...endpointItem.blockedActions,
      ...endpointItem.dataDomain,
    ]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
}

export function buildApiMarketStats(endpoints: ApiMarketEndpoint[]): ApiMarketStats {
  return {
    endpointCount: endpoints.length,
    fixtureReadyCount: endpoints.filter((endpointItem) => endpointItem.executionMode === "fixture_ready")
      .length,
    liveGatedCount: endpoints.filter((endpointItem) => endpointItem.executionMode !== "fixture_ready")
      .length,
    p0Count: endpoints.filter((endpointItem) => endpointItem.priority === "p0").length,
    platformCount: new Set(endpoints.map((endpointItem) => endpointItem.platform)).size,
    providerCallAttempted: false,
  };
}

function endpoint(input: EndpointInput): ApiMarketEndpoint {
  const profile = platformProfiles[input.platform];
  return {
    ...input,
    apiVersion: input.apiVersion ?? profile.apiVersion,
    authMode: input.authMode ?? profile.authMode,
    blockedActions: input.blockedActions ?? profile.blockedActions,
    costHint: input.costHint ?? profile.costHint,
    credentialReadAttempted: false,
    liveClientCreated: false,
    officialDocs: input.officialDocs?.length ? input.officialDocs : profile.officialDocs,
    platformLabel: input.platformLabel ?? profile.platformLabel,
    policyFlags: input.policyFlags ?? profile.policyFlags,
    priority: input.priority ?? profile.priority,
    productionWriteAllowed: false,
    providerCall: false,
    providerCallAttempted: false,
    providerId: input.providerId ?? profile.providerId,
    quotaHint: input.quotaHint ?? profile.quotaHint,
    requiredCredentials: input.requiredCredentials ?? profile.requiredCredentials,
    sdkPackage: input.sdkPackage ?? profile.sdkPackage,
    sdkStatus: input.sdkStatus ?? profile.sdkStatus,
    stability: input.stability ?? profile.stability,
  };
}

function parameter(
  name: string,
  location: "body" | "path" | "query",
  type: "array" | "boolean" | "number" | "object" | "string",
  required: boolean,
  description: string,
  example?: string,
) {
  return {
    description,
    example,
    in: location,
    name,
    required,
    type,
  };
}

function rawSample(providerId: string, endpointPath: string, schemaVersion: string) {
  return {
    sample: {
      evidence_ref: `fixture://${providerId}/${endpointPath}/1`,
      provider_call: false,
      provider_id: providerId,
      raw_record_id: `fixture:${providerId}:${endpointPath}:1`,
    },
    schemaVersion,
  };
}

function itemSample(providerId: string, endpointPath: string, schemaVersion: string) {
  return {
    sample: {
      author_policy: "hashed",
      evidence_ref: `fixture://${providerId}/${endpointPath}/1`,
      item_id: `social_item:${providerId}:${endpointPath}:1`,
      provider_call: false,
      provider_id: providerId,
    },
    schemaVersion,
  };
}
