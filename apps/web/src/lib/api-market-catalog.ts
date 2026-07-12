import { capabilityPlatformLabel } from "@/lib/capability-market";
import type {
  CapabilityAssertion,
  CapabilityImplementation,
  CapabilityStatus,
} from "@/types/capability";
import type {
  ApiMarketEndpoint,
  ApiMarketEndpointPresentation,
  ApiMarketFilterState,
  ApiMarketStats,
} from "@/types/api-market";

export const apiMarketEndpointPresentations: ApiMarketEndpointPresentation[] = [
  {
    category: "content_search",
    endpointId: "search.list",
    id: "youtube-v3-search-list",
    method: "GET",
    priority: "p0",
    providerId: "youtube.v3",
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
  },
  {
    category: "video_detail",
    endpointId: "videos.list",
    id: "youtube-v3-videos-list",
    method: "GET",
    priority: "p0",
    providerId: "youtube.v3",
    request: {
      parameters: [
        parameter("part", "query", "string", true, "Requested video fields.", "snippet,statistics"),
        parameter("id", "query", "string", true, "Comma-separated video ids.", "video_id"),
      ],
    },
    responsePreview: itemSample("youtube.v3", "videos.list", "social_post.v1"),
    summary: "Read official public video metadata for reviewed video ids.",
    title: "YouTube Video Detail",
  },
  {
    category: "creator_profile",
    endpointId: "channels.list",
    id: "youtube-v3-channels-list",
    method: "GET",
    priority: "p0",
    providerId: "youtube.v3",
    request: {
      parameters: [
        parameter("part", "query", "string", true, "Requested channel fields.", "snippet,statistics"),
        parameter("id", "query", "string", true, "Channel id.", "channel_id"),
      ],
    },
    responsePreview: itemSample("youtube.v3", "channels.list", "social_creator_snapshot.v1"),
    summary: "Read public channel metadata and creator snapshots from approved channel ids.",
    title: "YouTube Channel Snapshot",
  },
  {
    category: "comment_threads",
    endpointId: "commentThreads.list",
    id: "youtube-v3-commentthreads-list",
    method: "GET",
    priority: "p0",
    providerId: "youtube.v3",
    request: {
      parameters: [
        parameter("part", "query", "string", true, "Requested comment fields.", "snippet,replies"),
        parameter("videoId", "query", "string", true, "Video id.", "video_id"),
      ],
    },
    responsePreview: itemSample("youtube.v3", "commentThreads.list", "social_comment.v1"),
    summary: "Read public comment thread fixtures and prepare official comment collection gates.",
    title: "YouTube Comment Threads",
  },
  {
    category: "post_search",
    endpointId: "search",
    id: "reddit-praw-search",
    method: "GET",
    priority: "p1",
    providerId: "reddit.praw",
    request: {
      parameters: [
        parameter("q", "query", "string", true, "Search query.", "brand keyword"),
        parameter("subreddit", "query", "string", false, "Optional subreddit scope.", "skincareaddiction"),
      ],
    },
    responsePreview: itemSample("reddit.praw", "search", "social_voc_item.v1"),
    summary: "Search authorized Reddit public/community content through OAuth-scoped access.",
    title: "Reddit Search",
  },
  {
    category: "post_search",
    endpointId: "hot.list",
    id: "reddit-praw-hot-list",
    method: "GET",
    priority: "p1",
    providerId: "reddit.praw",
    request: {
      parameters: [
        parameter("subreddit", "query", "string", true, "Authorized subreddit scope.", "skincareaddiction"),
        parameter("limit", "query", "number", false, "Small fixture replay limit.", "5"),
      ],
    },
    responsePreview: itemSample("reddit.praw", "hot.list", "social_post.v1"),
    summary: "Review hot subreddit post collection through authorized OAuth boundaries.",
    title: "Reddit Hot Posts",
  },
  {
    category: "comment_threads",
    endpointId: "comments.new",
    id: "reddit-praw-comments-new",
    method: "GET",
    priority: "p1",
    providerId: "reddit.praw",
    request: {
      parameters: [
        parameter("subreddit", "query", "string", true, "Authorized subreddit scope.", "skincareaddiction"),
        parameter("limit", "query", "number", false, "Small fixture replay limit.", "5"),
      ],
    },
    responsePreview: itemSample("reddit.praw", "comments.new", "social_comment.v1"),
    summary: "Prepare read-only public comment review with no AI training or private data capture.",
    title: "Reddit New Comments",
  },
  {
    category: "post_search",
    endpointId: "tweets/search/recent",
    id: "x-v2-tweets-search-recent",
    method: "GET",
    priority: "p2",
    providerId: "x.v2",
    request: {
      parameters: [
        parameter("query", "query", "string", true, "Recent search query.", "brand keyword lang:en"),
        parameter("max_results", "query", "number", false, "Small approved page size.", "10"),
      ],
    },
    responsePreview: itemSample("x.v2", "tweets/search/recent", "social_post.v1"),
    summary: "Plan paid-tier recent search with cost budget and endpoint-specific rate gates.",
    title: "X Recent Search",
  },
  {
    category: "post_lookup",
    endpointId: "tweets",
    id: "x-v2-tweets",
    method: "GET",
    priority: "p2",
    providerId: "x.v2",
    request: {
      parameters: [
        parameter("ids", "query", "array", true, "Reviewed tweet ids.", "tweet_id"),
        parameter("tweet.fields", "query", "string", false, "Requested fields.", "created_at,public_metrics"),
      ],
    },
    responsePreview: itemSample("x.v2", "tweets", "social_post.v1"),
    summary: "Lookup reviewed X posts after paid access and budget approval.",
    title: "X Tweet Lookup",
  },
  {
    category: "media_feed",
    endpointId: "media",
    id: "instagram-graph-media",
    method: "GET",
    priority: "p2",
    providerId: "instagram_graph.v19",
    request: {
      parameters: [
        parameter("ig_user_id", "path", "string", true, "Owned or authorized Instagram business account id.", "17841400000000000"),
        parameter("fields", "query", "string", false, "Requested fields.", "id,caption,media_type,timestamp"),
      ],
    },
    responsePreview: itemSample("instagram_graph.v19", "media", "social_post.v1"),
    summary: "Review authorized business/creator media access through Meta Graph permissions.",
    title: "Instagram Media",
  },
  {
    category: "mentions",
    endpointId: "mentions",
    id: "instagram-graph-mentions",
    method: "GET",
    priority: "p2",
    providerId: "instagram_graph.v19",
    request: {
      parameters: [
        parameter("ig_user_id", "path", "string", true, "Owned or authorized Instagram business account id.", "17841400000000000"),
        parameter("fields", "query", "string", false, "Mention fields.", "caption,media_type,permalink"),
      ],
    },
    responsePreview: itemSample("instagram_graph.v19", "mentions", "social_voc_item.v1"),
    summary: "Plan limited mention monitoring for approved business assets only.",
    title: "Instagram Mentions",
  },
  {
    category: "insights",
    endpointId: "insights",
    id: "instagram-graph-insights",
    method: "GET",
    priority: "p2",
    providerId: "instagram_graph.v19",
    request: {
      parameters: [
        parameter("media_id", "path", "string", true, "Owned media id.", "media_id"),
        parameter("metric", "query", "string", true, "Approved insight metric.", "impressions,reach"),
      ],
    },
    responsePreview: itemSample("instagram_graph.v19", "insights", "social_topic_trend.v1"),
    summary: "Plan owned-asset insight collection after Meta app review.",
    title: "Instagram Insights",
  },
  {
    category: "media_feed",
    endpointId: "threads",
    id: "threads-graph-threads",
    method: "GET",
    priority: "p3",
    providerId: "threads.graph.v1",
    request: {
      parameters: [
        parameter("user_id", "path", "string", true, "Authorized Threads profile id.", "threads_user_id"),
        parameter("fields", "query", "string", false, "Requested fields.", "id,text,timestamp"),
      ],
    },
    responsePreview: itemSample("threads.graph.v1", "threads", "social_post.v1"),
    summary: "Plan authorized Threads content reads through Meta app permissions.",
    title: "Threads Feed",
  },
  {
    category: "comment_threads",
    endpointId: "replies",
    id: "threads-graph-replies",
    method: "GET",
    priority: "p3",
    providerId: "threads.graph.v1",
    request: {
      parameters: [
        parameter("thread_id", "path", "string", true, "Reviewed thread id.", "thread_id"),
        parameter("limit", "query", "number", false, "Small approved page size.", "5"),
      ],
    },
    responsePreview: itemSample("threads.graph.v1", "replies", "social_comment.v1"),
    summary: "Prepare reply review for authorized Threads assets only.",
    title: "Threads Replies",
  },
  {
    category: "research",
    endpointId: "video.search",
    id: "tiktok-research-video-search",
    method: "POST",
    priority: "p3",
    providerId: "tiktok_research",
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
  },
  {
    category: "comment_threads",
    endpointId: "comment.list",
    id: "tiktok-research-comment-list",
    method: "GET",
    priority: "p3",
    providerId: "tiktok_research",
    request: {
      parameters: [
        parameter("video_id", "query", "string", true, "Reviewed video id.", "video_id"),
        parameter("max_count", "query", "number", false, "Small approved page size.", "10"),
      ],
    },
    responsePreview: itemSample("tiktok_research", "comment.list", "social_comment.v1"),
    summary: "Plan research-only public comment review after qualification approval.",
    title: "TikTok Research Comments",
  },
  {
    category: "organization_updates",
    endpointId: "ugcPosts",
    id: "linkedin-mcdm-ugcposts",
    method: "GET",
    priority: "p3",
    providerId: "linkedin.mcdm",
    request: {
      parameters: [
        parameter("organization", "query", "string", true, "Authorized organization URN.", "urn:li:organization:123"),
        parameter("count", "query", "number", false, "Small approved page size.", "10"),
      ],
    },
    responsePreview: itemSample("linkedin.mcdm", "ugcPosts", "social_post.v1"),
    summary: "Prepare LinkedIn organization post review after product/tier approval.",
    title: "LinkedIn UGC Posts",
  },
  {
    category: "organization_updates",
    endpointId: "socialActions",
    id: "linkedin-mcdm-socialactions",
    method: "GET",
    priority: "p3",
    providerId: "linkedin.mcdm",
    request: {
      parameters: [
        parameter("activity", "query", "string", true, "Reviewed activity URN.", "urn:li:activity:123"),
        parameter("projection", "query", "string", false, "Approved projection.", "(comments,likes)"),
      ],
    },
    responsePreview: itemSample("linkedin.mcdm", "socialActions", "social_comment.v1"),
    summary: "Prepare LinkedIn social action reads with no contact graph expansion.",
    title: "LinkedIn Social Actions",
  },
];

const supportStatusPriority: CapabilityStatus[] = [
  "verified",
  "partial",
  "candidate",
  "blocked",
  "unsupported",
  "deprecated",
  "unknown",
];

export function assertApiMarketPresentationParity(
  presentations: ApiMarketEndpointPresentation[],
  implementations: CapabilityImplementation[],
): void {
  const implementationByProviderId = new Map<string, CapabilityImplementation>();
  for (const implementation of implementations) {
    if (implementationByProviderId.has(implementation.providerId)) {
      throw new Error("api_market_duplicate_provider_id");
    }
    implementationByProviderId.set(implementation.providerId, implementation);
  }

  const presentationKeys = new Set<string>();
  for (const presentation of presentations) {
    const key = endpointKey(presentation.providerId, presentation.endpointId);
    if (presentationKeys.has(key)) {
      throw new Error("api_market_duplicate_presentation_key");
    }
    presentationKeys.add(key);

    const implementation = implementationByProviderId.get(presentation.providerId);
    if (!implementation) {
      throw new Error("api_market_presentation_implementation_not_found");
    }
    if (!implementation.supportedEndpoints.includes(presentation.endpointId)) {
      throw new Error("api_market_presentation_endpoint_not_in_catalog");
    }
  }
}

export function composeApiMarketEndpoints(
  presentations: ApiMarketEndpointPresentation[],
  implementations: CapabilityImplementation[],
  assertions: CapabilityAssertion[],
): ApiMarketEndpoint[] {
  assertApiMarketPresentationParity(presentations, implementations);

  const presentationByKey = new Map(
    presentations.map((presentation) => [
      endpointKey(presentation.providerId, presentation.endpointId),
      presentation,
    ]),
  );

  return implementations.flatMap((implementation) => {
    const supportStatus = selectSupportStatus(
      assertions.filter(
        (assertion) =>
          assertion.implementation_id === implementation.implementationId,
      ),
    );

    return implementation.supportedEndpoints.map((endpointId): ApiMarketEndpoint => {
      const presentation = presentationByKey.get(
        endpointKey(implementation.providerId, endpointId),
      );
      const capabilityFacts = {
        accessChannel: implementation.accessChannel,
        apiVersion: implementation.apiVersion,
        authMode: implementation.authMode,
        blockedActions: implementation.blockedActions,
        costHint: formatCapabilityHint(implementation.costHint),
        credentialReadAttempted: false as const,
        dataDomains: implementation.dataDomains,
        endpoint: endpointId,
        liveClientCreated: false as const,
        officialDocs: implementation.officialDocs,
        platform: implementation.platform,
        platformLabel: capabilityPlatformLabel(implementation.platform),
        policyFlags: implementation.policyFlags,
        providerCall: false as const,
        providerCallAttempted: false as const,
        providerId: implementation.providerId,
        productionWriteAllowed: false as const,
        quotaHint: formatCapabilityHint(implementation.quotaHint),
        requiredCredentials: implementation.requiredCredentials,
        sdkPackage: implementation.sdkSelection?.package ?? null,
        sdkStatus: implementation.sdkSelection?.status ?? null,
        stability: implementation.stability,
        supportStatus,
      };

      if (presentation) {
        return {
          ...capabilityFacts,
          category: presentation.category,
          id: presentation.id,
          method: presentation.method,
          presentationMode: "enhanced",
          presentation,
          priority: presentation.priority,
          request: presentation.request,
          responsePreview: presentation.responsePreview,
          summary: presentation.summary,
          title: presentation.title,
        };
      }

      return {
        ...capabilityFacts,
        category: null,
        id: `generic:${implementation.implementationId}:${endpointId}`,
        method: null,
        presentationMode: "generic",
        presentation: null,
        priority: null,
        request: null,
        responsePreview: null,
        summary: "无展示增强；仅显示规范能力事实",
        title: endpointId,
      };
    });
  });
}

export function findApiMarketPresentationById(
  endpointId: string,
): ApiMarketEndpointPresentation | null {
  return (
    apiMarketEndpointPresentations.find(
      (presentation) => presentation.id === endpointId,
    ) ?? null
  );
}

export function listApiMarketPresentationsByProviderId(
  providerId: string,
): ApiMarketEndpointPresentation[] {
  return apiMarketEndpointPresentations.filter(
    (presentation) => presentation.providerId === providerId,
  );
}

export function findApiMarketEndpointById(
  endpoints: ApiMarketEndpoint[],
  id: string,
): ApiMarketEndpoint | null {
  return endpoints.find((endpointItem) => endpointItem.id === id) ?? null;
}

export function filterApiMarketEndpoints(
  endpoints: ApiMarketEndpoint[],
  filters: ApiMarketFilterState,
): ApiMarketEndpoint[] {
  const query = filters.query.trim().toLowerCase();
  return endpoints.filter((endpointItem) => {
    if (
      filters.accessChannel !== "all" &&
      endpointItem.accessChannel !== filters.accessChannel
    ) {
      return false;
    }
    if (filters.platform !== "all" && endpointItem.platform !== filters.platform) {
      return false;
    }
    if (filters.category !== "all" && endpointItem.category !== filters.category) {
      return false;
    }
    if (filters.priority !== "all" && endpointItem.priority !== filters.priority) {
      return false;
    }
    if (filters.status !== "all" && endpointItem.supportStatus !== filters.status) {
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
    ]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
}

export function buildApiMarketStats(endpoints: ApiMarketEndpoint[]): ApiMarketStats {
  return {
    candidateCount: endpoints.filter(
      (endpointItem) => endpointItem.supportStatus === "candidate",
    ).length,
    endpointCount: endpoints.length,
    platformCount: new Set(endpoints.map((endpointItem) => endpointItem.platform)).size,
    providerCallAttempted: false,
    unknownCount: endpoints.filter(
      (endpointItem) => endpointItem.supportStatus === "unknown",
    ).length,
    verifiedCount: endpoints.filter(
      (endpointItem) => endpointItem.supportStatus === "verified",
    ).length,
  };
}

function endpointKey(providerId: string, endpointId: string): string {
  return `${providerId}\0${endpointId}`;
}

function selectSupportStatus(assertions: CapabilityAssertion[]): CapabilityStatus {
  const ownedStatuses = new Set(
    assertions.map((assertion) => assertion.support_status),
  );
  return (
    supportStatusPriority.find((status) => ownedStatuses.has(status)) ?? "unknown"
  );
}

function formatCapabilityHint(hint: Record<string, unknown>): string {
  return Object.keys(hint)
    .sort()
    .map((key) => {
      const value = hint[key];
      const rendered =
        typeof value === "object" && value !== null
          ? JSON.stringify(value)
          : String(value);
      return `${key}=${rendered}`;
    })
    .join("; ");
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
