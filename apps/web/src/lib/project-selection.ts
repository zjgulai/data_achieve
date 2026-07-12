import type { Project } from "@/types/project";

export const selectedProjectStorageKey =
  "data-intelligence-hub:selected-project-id";

export type SelectedProjectPreference = {
  available: boolean;
  value: string | null;
};

export function resolveSelectedProjectId(
  projects: Project[],
  storedProjectId: string | null,
): string | null {
  if (!storedProjectId) {
    return null;
  }
  return projects.some(
    (project) =>
      project.id === storedProjectId && project.status === "active",
  )
    ? storedProjectId
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
      new CustomEvent("data-intelligence-hub:project-selection", {
        detail: { projectId: value },
      }),
    );
  } catch {
    // Storage is already consistent; the event is only a same-page hint.
  }
  return true;
}
