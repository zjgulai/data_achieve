export const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const mockApiEnabled = process.env.NEXT_PUBLIC_MOCK_API === "true";

export type ApiValidationIssue = {
  loc: Array<string | number>;
  msg: string;
  type?: string;
};

export type ApiErrorCode =
  | "authentication_required"
  | "workflow_plan_not_found"
  | "workflow_version_not_found"
  | "project_not_active"
  | "preview_stale"
  | "version_conflict"
  | "idempotency_conflict"
  | "workflow_plan_flow_mode_conflict"
  | "validation_error"
  | "capability_catalog_load_failed"
  | "workflow_planner_dependency_unavailable"
  | "persistence_unavailable"
  | "workflow_planner_invalid_step_graph"
  | "workflow_planner_internal_error";

export type ApiErrorRecoveryDetails = {
  projectId?: string;
  workflowPlanId?: string;
  expectedCurrentVersionId?: string;
  currentVersionId?: string;
  currentVersionNumber?: number;
  expectedPreviewFingerprint?: string;
  actualPreviewFingerprint?: string;
};

const stableApiErrorCodes = new Set<ApiErrorCode>([
  "authentication_required",
  "workflow_plan_not_found",
  "workflow_version_not_found",
  "project_not_active",
  "preview_stale",
  "version_conflict",
  "idempotency_conflict",
  "workflow_plan_flow_mode_conflict",
  "validation_error",
  "capability_catalog_load_failed",
  "workflow_planner_dependency_unavailable",
  "persistence_unavailable",
  "workflow_planner_invalid_step_graph",
  "workflow_planner_internal_error",
]);
const recoveryDetailErrorCodes = new Set<ApiErrorCode>([
  "preview_stale",
  "version_conflict",
]);

export class ApiRequestError extends Error {
  status: number;
  validationIssues: ApiValidationIssue[];
  requestId: string | null;
  code: ApiErrorCode | null;
  details: ApiErrorRecoveryDetails;

  constructor(
    status: number,
    message: string,
    options: {
      validationIssues?: ApiValidationIssue[];
      requestId?: string | null;
      code?: ApiErrorCode | string | null;
      details?: unknown;
    } = {},
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.validationIssues = options.validationIssues ?? [];
    this.requestId = options.requestId ?? null;
    this.code =
      readStableApiErrorCode(options.code) ?? readStableApiErrorCode(message);
    this.details =
      this.code && recoveryDetailErrorCodes.has(this.code)
        ? readApiErrorRecoveryDetails(options.details)
        : {};
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const error = await readApiError(response);
    if (response.status === 401 && shouldRedirectForUnauthorized(path)) {
      redirectToLogin();
    }
    throw new ApiRequestError(response.status, error.message, {
      validationIssues: error.validationIssues,
      requestId: response.headers.get("x-request-id"),
      code: error.code,
      details: error.details,
    });
  }

  return response.json() as Promise<T>;
}

async function readApiError(response: Response): Promise<{
  message: string;
  validationIssues: ApiValidationIssue[];
  code: ApiErrorCode | null;
  details: ApiErrorRecoveryDetails;
}> {
  const fallback = `API request failed: ${response.status}`;
  const fallbackError = {
    message: fallback,
    validationIssues: [],
    code: null,
    details: {},
  } satisfies {
    message: string;
    validationIssues: ApiValidationIssue[];
    code: ApiErrorCode | null;
    details: ApiErrorRecoveryDetails;
  };
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return fallbackError;
  }

  try {
    const body = (await response.json()) as unknown;
    if (typeof body === "string" && body.trim().length > 0) {
      return buildApiErrorMetadata(body);
    }
    if (!isRecord(body)) {
      return fallbackError;
    }
    if (typeof body.detail === "string" && body.detail.trim().length > 0) {
      return buildApiErrorMetadata(body.detail, body.code, body.details);
    }
    if (!Array.isArray(body.detail) && isRecord(body.detail)) {
      const code = readStableApiErrorCode(body.detail.code ?? body.code);
      const message =
        code ?? readNonEmptyString(body.detail.message) ?? fallback;
      return buildApiErrorMetadata(
        message,
        code,
        body.detail.details ?? body.details,
      );
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      const detailMessages = body.detail.flatMap((item) =>
        isRecord(item) && typeof item.msg === "string" ? [item.msg] : [],
      );
      const validationIssues = body.detail.flatMap((item) => {
        if (
          !isRecord(item) ||
          !Array.isArray(item.loc) ||
          item.loc.length === 0 ||
          !item.loc.every(
            (part): part is string | number =>
              typeof part === "string" || typeof part === "number",
          ) ||
          typeof item.msg !== "string"
        ) {
          return [];
        }
        return [
          {
            loc: item.loc,
            msg: item.msg,
            ...(typeof item.type === "string" ? { type: item.type } : {}),
          },
        ];
      });
      const message = detailMessages.join("; ");
      return {
        message: message.length > 0 ? message : fallback,
        validationIssues,
        code: null,
        details: {},
      };
    }
    if (typeof body.message === "string" && body.message.trim().length > 0) {
      return buildApiErrorMetadata(body.message, body.code, body.details);
    }
  } catch {
    return fallbackError;
  }
  return fallbackError;
}

function buildApiErrorMetadata(
  message: string,
  codeCandidate?: unknown,
  detailsCandidate?: unknown,
): {
  message: string;
  validationIssues: ApiValidationIssue[];
  code: ApiErrorCode | null;
  details: ApiErrorRecoveryDetails;
} {
  const code =
    readStableApiErrorCode(codeCandidate) ?? readStableApiErrorCode(message);
  return {
    message,
    validationIssues: [],
    code,
    details:
      code && recoveryDetailErrorCodes.has(code)
        ? readApiErrorRecoveryDetails(detailsCandidate)
        : {},
  };
}

function readStableApiErrorCode(value: unknown): ApiErrorCode | null {
  return typeof value === "string" &&
    stableApiErrorCodes.has(value as ApiErrorCode)
    ? (value as ApiErrorCode)
    : null;
}

function readApiErrorRecoveryDetails(value: unknown): ApiErrorRecoveryDetails {
  if (!isRecord(value)) {
    return {};
  }

  const details: ApiErrorRecoveryDetails = {};
  assignBoundedString(
    details,
    "projectId",
    value.project_id ?? value.projectId,
  );
  assignBoundedString(
    details,
    "workflowPlanId",
    value.workflow_plan_id ?? value.workflowPlanId,
  );
  assignBoundedString(
    details,
    "expectedCurrentVersionId",
    value.expected_current_version_id ?? value.expectedCurrentVersionId,
  );
  assignBoundedString(
    details,
    "currentVersionId",
    value.current_version_id ?? value.currentVersionId,
  );
  assignBoundedString(
    details,
    "expectedPreviewFingerprint",
    value.expected_preview_fingerprint ?? value.expectedPreviewFingerprint,
  );
  assignBoundedString(
    details,
    "actualPreviewFingerprint",
    value.actual_preview_fingerprint ?? value.actualPreviewFingerprint,
  );
  const currentVersionNumber =
    value.current_version_number ?? value.currentVersionNumber;
  if (
    typeof currentVersionNumber === "number" &&
    Number.isSafeInteger(currentVersionNumber) &&
    currentVersionNumber >= 1
  ) {
    details.currentVersionNumber = currentVersionNumber;
  }
  return details;
}

function assignBoundedString(
  target: ApiErrorRecoveryDetails,
  key: keyof ApiErrorRecoveryDetails,
  value: unknown,
) {
  if (typeof value === "string" && value.length > 0 && value.length <= 256) {
    Object.assign(target, { [key]: value });
  }
}

function readNonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function shouldRedirectForUnauthorized(path: string) {
  return path !== "/api/auth/login" && path !== "/api/auth/register";
}

function redirectToLogin() {
  if (typeof window === "undefined" || window.location.pathname === "/login") {
    return;
  }
  const next = `${window.location.pathname}${window.location.search}`;
  window.location.assign(`/login?next=${encodeURIComponent(next)}`);
}
