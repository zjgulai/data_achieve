export const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const mockApiEnabled = process.env.NEXT_PUBLIC_MOCK_API === "true";

export class ApiRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const message = await readApiErrorMessage(response);
    if (response.status === 401 && shouldRedirectForUnauthorized(path)) {
      redirectToLogin();
    }
    throw new ApiRequestError(response.status, message);
  }

  return response.json() as Promise<T>;
}

async function readApiErrorMessage(response: Response): Promise<string> {
  const fallback = `API request failed: ${response.status}`;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return fallback;
  }

  try {
    const body = (await response.json()) as {
      detail?: string | Array<{ msg?: string }>;
      message?: string;
    };
    if (typeof body.detail === "string" && body.detail.trim().length > 0) {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      return body.detail
        .map((item) => item.msg)
        .filter((message): message is string => Boolean(message))
        .join("; ");
    }
    if (typeof body.message === "string" && body.message.trim().length > 0) {
      return body.message;
    }
  } catch {
    return fallback;
  }
  return fallback;
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
