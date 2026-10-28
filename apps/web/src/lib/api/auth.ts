import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockAuthSession } from "@/lib/api/mock";
import type { AuthSession } from "@/types/project";

export type AuthPayload = {
  email: string;
  password: string;
  name?: string;
};

type AuthSessionResponse = {
  user: {
    id: string;
    email: string;
    name: string;
    status: string;
  };
  workspace: {
    id: string;
    name: string;
    slug: string;
    owner_id: string;
  };
};

export async function login(payload: AuthPayload): Promise<AuthSession> {
  if (mockApiEnabled) {
    return getMockAuthSession(payload.email, payload.name);
  }
  const response = await apiFetch<AuthSessionResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email: payload.email, password: payload.password }),
  });
  return mapAuthSession(response);
}

export async function register(payload: Required<AuthPayload>): Promise<AuthSession> {
  if (mockApiEnabled) {
    return getMockAuthSession(payload.email, payload.name);
  }
  const response = await apiFetch<AuthSessionResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return mapAuthSession(response);
}

/** 读取当前会话。未登录时后端返回 401，调用方需要处理。 */
export async function fetchAuthSession(): Promise<AuthSession> {
  if (mockApiEnabled) {
    return getMockAuthSession("demo@example.com", "Demo");
  }
  const response = await apiFetch<AuthSessionResponse>("/api/auth/me");
  return mapAuthSession(response);
}

/** 退出登录。后端清 cookie 并返回 204。 */
export async function logout(): Promise<void> {
  if (mockApiEnabled) {
    return;
  }
  await apiFetch<void>("/api/auth/logout", { method: "POST" });
}

function mapAuthSession(response: AuthSessionResponse): AuthSession {
  return {
    user: response.user,
    workspace: {
      id: response.workspace.id,
      name: response.workspace.name,
      slug: response.workspace.slug,
      ownerId: response.workspace.owner_id,
    },
  };
}
