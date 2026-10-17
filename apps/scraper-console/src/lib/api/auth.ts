import { apiFetch } from "./client";

/** 用户。字段与服务端 schemas/auth.py:UserResponse 一致。 */
export type AuthUser = Readonly<{
  id: string;
  email: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
}>;

/** 工作区。字段与服务端 schemas/auth.py:WorkspaceResponse 一致。 */
export type AuthWorkspace = Readonly<{
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}>;

/** 当前会话。 */
export type AuthSession = Readonly<{
  user: AuthUser;
  workspace: AuthWorkspace;
}>;

/**
 * 读取当前会话。
 *
 * 服务端要求有效的 access_token Cookie，否则返回 401。
 * console 目前没有登录界面，故调用方必须处理 401。
 */
export function fetchAuthSession(): Promise<AuthSession> {
  return apiFetch<AuthSession>("/api/auth/me");
}
