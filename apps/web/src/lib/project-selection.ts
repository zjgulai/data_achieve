import type { Project } from "@/types/project";

export const selectedProjectStorageKey =
  "data-intelligence-hub:selected-project-id";
export const projectSelectionEventName =
  "data-intelligence-hub:project-selection";
export const projectSelectionRequestEventName =
  "data-intelligence-hub:project-selection-request";
export const selectedProjectQueryKey = "project_id";

export type SelectedProjectPreference = {
  available: boolean;
  value: string | null;
};

const workflowPlanDetailPathPattern =
  /^\/automation\/projects\/([^/]+)\/plans\/[^/]+\/?$/;

export function resolveRouteScopedProjectId(pathname: string): string | null {
  const encodedProjectId = workflowPlanDetailPathPattern.exec(pathname)?.[1];
  if (!encodedProjectId) {
    return null;
  }
  try {
    return decodeURIComponent(encodedProjectId);
  } catch {
    return encodedProjectId;
  }
}

export function readProjectIdFromSearch(search: string): string | null {
  const value = new URLSearchParams(search).get(selectedProjectQueryKey);
  return value?.trim() || null;
}

export function projectSelectionRelativeUrl(
  currentUrl: string,
  projectId: string | null,
): string {
  const url = new URL(currentUrl, "http://localhost");
  if (projectId) {
    url.searchParams.set(selectedProjectQueryKey, projectId);
  } else {
    url.searchParams.delete(selectedProjectQueryKey);
  }
  return `${url.pathname}${url.search}${url.hash}`;
}

export function projectFilterStatusMessage({
  pathname,
  selectedProjectId,
  filterApplied,
}: {
  pathname: string;
  selectedProjectId: string | null;
  filterApplied: boolean;
}): string {
  const routeProjectId = resolveRouteScopedProjectId(pathname);
  if (routeProjectId) {
    const preference = selectedProjectId ? ` ${selectedProjectId} ` : "";
    return `当前页面按 URL Project ${routeProjectId} 读取；顶部项目偏好${preference}不影响本页`;
  }
  return filterApplied
    ? "当前页面已应用项目过滤"
    : "当前页面未应用项目过滤（全局数据）";
}

export function isProjectFilterApplied({
  pathname,
  selectedProjectId,
  appliedProjectId,
}: {
  pathname: string;
  selectedProjectId: string | null;
  appliedProjectId: string | null;
}): boolean {
  return (
    (pathname === "/dashboard" ||
      pathname.startsWith("/domain/") ||
      pathname === "/intelligence" ||
      pathname.startsWith("/intelligence/") ||
      pathname === "/automation/planner" ||
      pathname === "/automation/plans") &&
    selectedProjectId !== null &&
    selectedProjectId === appliedProjectId
  );
}

export function resolveSelectedProjectId(
  projects: Project[],
  storedProjectId: string | null,
): string | null {
  if (!storedProjectId) {
    return null;
  }
  return projects.some(
    (project) => project.id === storedProjectId && project.status === "active",
  )
    ? storedProjectId
    : null;
}

export function resolveAppliedProjectId(
  projects: Project[],
  selectedProjectId: string | null,
  previewProjectId: string,
): string | null {
  const activePreviewProjectId = resolveSelectedProjectId(
    projects,
    previewProjectId,
  );
  return activePreviewProjectId !== null &&
    activePreviewProjectId === selectedProjectId
    ? activePreviewProjectId
    : null;
}

export function readSelectedProjectId(): string | null {
  return readSelectedProjectPreference().value;
}

export function readSelectedProjectPreference(): SelectedProjectPreference {
  if (typeof window === "undefined") {
    return { available: false, value: null };
  }
  try {
    return {
      available: true,
      value: window.localStorage.getItem(selectedProjectStorageKey),
    };
  } catch {
    return { available: false, value: null };
  }
}

export function writeSelectedProjectId(value: string | null): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  try {
    if (value) {
      window.localStorage.setItem(selectedProjectStorageKey, value);
    } else {
      window.localStorage.removeItem(selectedProjectStorageKey);
    }
  } catch {
    return false;
  }
  try {
    window.dispatchEvent(
      new CustomEvent(projectSelectionEventName, {
        detail: { projectId: value },
      }),
    );
  } catch {
    // Storage is already consistent; the event is only a same-page hint.
  }
  return true;
}
