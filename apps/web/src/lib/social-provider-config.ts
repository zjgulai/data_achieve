import type { SocialProviderPlatform } from "@/types/social-provider";

export type SocialProviderEndpointOption = {
  label: string;
  value: string;
};

export type SocialProviderUiConfig = {
  platform: SocialProviderPlatform;
  label: string;
  providerId: string;
  endpoints: SocialProviderEndpointOption[];
};

export const socialProviderUiConfigs: SocialProviderUiConfig[] = [
  {
    platform: "youtube",
    label: "YouTube",
    providerId: "youtube.v3",
    endpoints: [
      { label: "search.list", value: "search.list" },
      { label: "videos.list", value: "videos.list" },
      { label: "channels.list", value: "channels.list" },
      { label: "commentThreads.list", value: "commentThreads.list" },
    ],
  },
  {
    platform: "reddit",
    label: "Reddit",
    providerId: "reddit.praw",
    endpoints: [
      { label: "hot.list", value: "hot.list" },
      { label: "new.list", value: "new.list" },
      { label: "search", value: "search" },
      { label: "comments.new", value: "comments.new" },
      { label: "r/{subreddit}/about", value: "r/{subreddit}/about" },
    ],
  },
  {
    platform: "x",
    label: "X",
    providerId: "x.v2",
    endpoints: [
      { label: "tweets/search/recent", value: "tweets/search/recent" },
      { label: "tweets", value: "tweets" },
      { label: "users/me", value: "users/me" },
      { label: "users/by/username/:id", value: "users/by/username/:id" },
    ],
  },
  {
    platform: "instagram",
    label: "Instagram",
    providerId: "instagram_graph.v19",
    endpoints: [
      { label: "media", value: "media" },
      { label: "user_media", value: "user_media" },
      { label: "mentions", value: "mentions" },
      { label: "comments", value: "comments" },
      { label: "insights", value: "insights" },
    ],
  },
  {
    platform: "threads",
    label: "Threads",
    providerId: "threads.graph.v1",
    endpoints: [
      { label: "threads", value: "threads" },
      { label: "users", value: "users" },
      { label: "mentions", value: "mentions" },
      { label: "media", value: "media" },
      { label: "replies", value: "replies" },
    ],
  },
  {
    platform: "tiktok",
    label: "TikTok Research",
    providerId: "tiktok_research",
    endpoints: [
      { label: "video.search", value: "video.search" },
      { label: "video.list", value: "video.list" },
      { label: "comment.list", value: "comment.list" },
      { label: "user.info", value: "user.info" },
      { label: "vce.batch_status", value: "vce.batch_status" },
    ],
  },
  {
    platform: "linkedin",
    label: "LinkedIn",
    providerId: "linkedin.mcdm",
    endpoints: [
      { label: "ugcPosts", value: "ugcPosts" },
      { label: "organizations", value: "organizations" },
      { label: "shares", value: "shares" },
      { label: "socialActions", value: "socialActions" },
      { label: "network_sizes", value: "network_sizes" },
    ],
  },
];

export function getSocialProviderUiConfig(
  platform: SocialProviderPlatform,
): SocialProviderUiConfig {
  const config = socialProviderUiConfigs.find((candidate) => candidate.platform === platform);
  if (!config) {
    throw new Error(`Unsupported social provider platform: ${platform}`);
  }
  return config;
}

export function getDefaultEndpointForPlatform(platform: SocialProviderPlatform): string {
  return getSocialProviderUiConfig(platform).endpoints[0]?.value ?? "";
}
