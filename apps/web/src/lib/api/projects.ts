import { apiFetch, mockApiEnabled } from "@/lib/api/client";
import { getMockProjects } from "@/lib/api/mock";
import type {
  Project,
  ProjectCreateInput,
  ProjectDomain,
  ProjectStatus,
} from "@/types/project";

type ProjectResponse = {
  id: string;
  name: string;
  description: string | null;
  domain: string;
  status: string;
};

const projectDomains = new Set<ProjectDomain>([
  "osint",
  "ecommerce",
  "social",
  "competitor",
  "agent",
  "platform",
  "governance",
  "mixed",
]);

const projectStatuses = new Set<ProjectStatus>(["active", "archived"]);

export async function listProjects(): Promise<Project[]> {
  if (mockApiEnabled) {
    return getMockProjects();
  }
  const response = await apiFetch<ProjectResponse[]>("/api/projects");
  return response.map(mapProject);
}

export async function createProject(payload: ProjectCreateInput): Promise<Project> {
  if (mockApiEnabled) {
    return {
      id: `project_${Date.now()}`,
      name: payload.name,
      description: payload.description ?? null,
      domain: payload.domain,
      status: "active",
      intelligenceCount: 0,
      sourceCount: 0,
    };
  }
  const response = await apiFetch<ProjectResponse>("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return mapProject(response);
}

function mapProject(response: ProjectResponse): Project {
  return {
    id: response.id,
    name: response.name,
    description: response.description,
    domain: normalizeProjectDomain(response.domain),
    status: normalizeProjectStatus(response.status),
    intelligenceCount: 0,
    sourceCount: 0,
  };
}

function normalizeProjectDomain(value: string): ProjectDomain {
  return projectDomains.has(value as ProjectDomain)
    ? (value as ProjectDomain)
    : "mixed";
}

function normalizeProjectStatus(value: string): ProjectStatus {
  return projectStatuses.has(value as ProjectStatus)
    ? (value as ProjectStatus)
    : "active";
}
