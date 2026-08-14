import { apiFetch } from "./client";

export type ProjectDomain = "osint" | "ecommerce" | "social" | "competitor" | "mixed";

export type Project = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  domain: ProjectDomain;
  status: "active" | "archived";
  owner_id: string;
  created_at: string;
  updated_at: string;
};

export type ProjectCreateRequest = {
  name: string;
  description?: string;
  domain: ProjectDomain;
};

export const DOMAIN_LABELS: Record<ProjectDomain, string> = {
  social:     "社媒监测",
  ecommerce:  "电商分析",
  competitor: "竞品追踪",
  osint:      "开源情报",
  mixed:      "综合项目",
};

export const DOMAIN_COLORS: Record<ProjectDomain, string> = {
  social:     "bg-[var(--accent-2-soft)] text-[var(--state-info)]",
  ecommerce:  "bg-[var(--success-soft)] text-[var(--state-success)]",
  competitor: "bg-[var(--accent-1-soft)] text-[var(--action-primary)]",
  osint:      "bg-[var(--warning-soft)] text-[var(--state-warning)]",
  mixed:      "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
};

export async function fetchProjects(): Promise<Project[]> {
  return apiFetch<Project[]>("/api/projects");
}

export async function fetchProject(id: string): Promise<Project> {
  return apiFetch<Project>(`/api/projects/${id}`);
}

export async function createProject(payload: ProjectCreateRequest): Promise<Project> {
  return apiFetch<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function archiveProject(id: string): Promise<Project> {
  return apiFetch<Project>(`/api/projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status: "archived" }),
  });
}
