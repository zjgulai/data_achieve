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
export type ApiMarketSdkStatus = "candidate" | "manual_review" | "selected";
export type ApiMarketMethod = "GET" | "POST" | "READ";

export type ApiMarketParameter = {
  description: string;
  example?: string;
  in: "body" | "path" | "query";
  name: string;
  required: boolean;
  type: "array" | "boolean" | "number" | "object" | "string";
};

export type ApiMarketEndpoint = {
  apiVersion: string;
  authMode: string;
  blockedActions: string[];
  category: ApiMarketCategory;
  costHint: string;
  credentialReadAttempted: false;
  dataDomain: string[];
  endpoint: string;
  executionMode: ApiMarketExecutionMode;
  id: string;
  liveClientCreated: false;
  method: ApiMarketMethod;
  officialDocs: string[];
  platform: ApiMarketPlatform;
  platformLabel: string;
  policyFlags: string[];
  priority: ApiMarketPriority;
  productionWriteAllowed: false;
  providerCall: false;
  providerCallAttempted: false;
  providerId: string;
  quotaHint: string;
  request: {
    parameters: ApiMarketParameter[];
    requestBodyExample?: Record<string, unknown>;
  };
  requiredCredentials: string[];
  responsePreview: {
    sample: Record<string, unknown>;
    schemaVersion: string;
  };
  sdkPackage: string;
  sdkStatus: ApiMarketSdkStatus;
  stability: ApiMarketStability;
  summary: string;
  title: string;
};

export type ApiMarketFilterState = {
  category: ApiMarketCategory | "all";
  executionMode: ApiMarketExecutionMode | "all";
  platform: ApiMarketPlatform | "all";
  priority: ApiMarketPriority | "all";
  query: string;
  stability: ApiMarketStability | "all";
};

export type ApiMarketStats = {
  endpointCount: number;
  fixtureReadyCount: number;
  liveGatedCount: number;
  p0Count: number;
  platformCount: number;
  providerCallAttempted: false;
};
