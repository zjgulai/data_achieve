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

/** 工作区与当前用户在该工作区的角色。 */
export type WorkspaceMembership = AuthWorkspace & Readonly<{ role: string }>;

/** 工作区成员。 */
export type WorkspaceMember = Readonly<{
  user: AuthUser;
  role: string;
}>;

/** 读取当前会话。未登录时服务端返回 401。 */
export function fetchAuthSession(): Promise<AuthSession> {
  return apiFetch<AuthSession>("/api/auth/me");
}

export function login(payload: {
  email: string;
  password: string;
}): Promise<AuthSession> {
  return apiFetch<AuthSession>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout(): Promise<void> {
  return apiFetch<void>("/api/auth/logout", { method: "POST" });
}

/** 列出当前用户加入的全部工作区。 */
export function fetchWorkspaces(): Promise<WorkspaceMembership[]> {
  return apiFetch<WorkspaceMembership[]>("/api/workspaces");
}

/** 切换当前工作区。服务端校验成员关系后写 Cookie。 */
export function activateWorkspace(workspaceId: string): Promise<AuthSession> {
  return apiFetch<AuthSession>(`/api/workspaces/${workspaceId}/activate`, {
    method: "POST",
  });
}

/** 当前工作区成员。 */
export function fetchWorkspaceMembers(): Promise<WorkspaceMember[]> {
  return apiFetch<WorkspaceMember[]>("/api/workspaces/current/members");
}

/** 按邮箱添加成员。仅工作区所有者可调用。 */
export function addWorkspaceMember(email: string): Promise<WorkspaceMember> {
  return apiFetch<WorkspaceMember>("/api/workspaces/current/members", {
    method: "POST",
    body: JSON.stringify({ email, role: "member" }),
  });
}

/** 移除成员。成员传自己的用户 ID 即退出工作区。 */
export function removeWorkspaceMember(userId: string): Promise<void> {
  return apiFetch<void>(`/api/workspaces/current/members/${userId}`, {
    method: "DELETE",
  });
}
