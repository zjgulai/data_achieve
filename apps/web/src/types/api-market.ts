import type {
  CapabilityAccessChannel,
  CapabilityPlatform,
  CapabilityStatus,
} from "@/types/capability";

export type ApiMarketPlatform = CapabilityPlatform;

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
export type ApiMarketMethod = "GET" | "POST" | "READ";

export type ApiMarketParameter = {
  description: string;
  example?: string;
  in: "body" | "path" | "query";
  name: string;
  required: boolean;
  type: "array" | "boolean" | "number" | "object" | "string";
};

type ApiMarketRequest = {
  parameters: ApiMarketParameter[];
  requestBodyExample?: Record<string, unknown>;
};

type ApiMarketResponsePreview = {
  sample: Record<string, unknown>;
  schemaVersion: string;
};

export type ApiMarketEndpointPresentation = {
  category: ApiMarketCategory;
  endpointId: string;
  id: string;
  method: ApiMarketMethod;
  priority: ApiMarketPriority;
  providerId: string;
  request: ApiMarketRequest;
  responsePreview: ApiMarketResponsePreview;
  summary: string;
  title: string;
};

type ApiMarketCapabilityFields = {
  accessChannel: CapabilityAccessChannel;
  apiVersion: string;
  authMode: string;
  blockedActions: string[];
  costHint: string;
  credentialReadAttempted: false;
  dataDomains: string[];
  endpoint: string;
  id: string;
  liveClientCreated: false;
  officialDocs: string[];
  platform: CapabilityPlatform;
  platformLabel: string;
  policyFlags: string[];
  providerCall: false;
  providerCallAttempted: false;
  providerId: string;
  productionWriteAllowed: false;
  quotaHint: string;
  requiredCredentials: string[];
  sdkPackage: string | null;
  sdkStatus: "selected" | "candidate" | "manual_review" | "blocked" | null;
  stability: ApiMarketStability;
  summary: string;
  supportStatus: CapabilityStatus;
  title: string;
};

export type ApiMarketEnhancedEndpoint = ApiMarketCapabilityFields & {
  category: ApiMarketCategory;
  method: ApiMarketMethod;
  presentationMode: "enhanced";
  presentation: ApiMarketEndpointPresentation;
  priority: ApiMarketPriority;
  request: ApiMarketRequest;
  responsePreview: ApiMarketResponsePreview;
};

export type ApiMarketGenericEndpoint = ApiMarketCapabilityFields & {
  category: null;
  method: null;
  presentationMode: "generic";
  presentation: null;
  priority: null;
  request: null;
  responsePreview: null;
};

export type ApiMarketEndpoint =
  | ApiMarketEnhancedEndpoint
  | ApiMarketGenericEndpoint;

export type ApiMarketFilterState = {
  accessChannel: CapabilityAccessChannel | "all";
  category: ApiMarketCategory | "all";
  platform: CapabilityPlatform | "all";
  priority: ApiMarketPriority | "all";
  query: string;
  status: CapabilityStatus | "all";
};

export type ApiMarketStats = {
  candidateCount: number;
  endpointCount: number;
  platformCount: number;
  providerCallAttempted: false;
  unknownCount: number;
  verifiedCount: number;
};
