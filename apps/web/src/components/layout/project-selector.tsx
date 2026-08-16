"use client";

import { usePathname } from "next/navigation";

import { useProjectSelection } from "@/components/layout/project-selection-provider";
import {
  projectFilterStatusMessage,
  projectSelectionRelativeUrl,
  projectSelectionRequestEventName,
  resolveRouteScopedProjectId,
} from "@/lib/project-selection";

export function ProjectSelector() {
  const pathname = usePathname();
  const {
    projects,
    selectedProjectId,
    loading,
    projectListError,
    preferenceError,
    filterApplied,
    selectProject,
  } = useProjectSelection();
  const routeProjectId = resolveRouteScopedProjectId(pathname);
  const statusMessage = projectFilterStatusMessage({
    pathname,
    selectedProjectId,
    filterApplied,
  });

  function requestProjectSelection(projectId: string | null): boolean {
    const request = new CustomEvent(projectSelectionRequestEventName, {
      cancelable: true,
      detail: { projectId, previousProjectId: selectedProjectId },
    });
    if (!window.dispatchEvent(request)) {
      return false;
    }
    selectProject(projectId);
    if (!routeProjectId) {
      const nextUrl = projectSelectionRelativeUrl(
        window.location.href,
        projectId,
      );
      const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (nextUrl !== currentUrl) {
        window.history.pushState(window.history.state, "", nextUrl);
      }
    }
    return true;
  }

  return (
    <div
      className="min-w-0 rounded-[var(--radius-2)] border border-[var(--border-subtle)] bg-[var(--surface-secondary)] px-3 py-2"
      data-project-filter-applied={String(filterApplied)}
      data-route-project-id={routeProjectId ?? undefined}
    >
      <label className="flex min-w-0 items-center gap-2 text-xs font-semibold text-[var(--text-secondary)]">
        <span className="shrink-0">{routeProjectId ? "项目偏好" : "项目"}</span>
        <select
          aria-describedby="global-project-filter-status"
          className="min-h-[var(--touch-target)] min-w-0 max-w-48 rounded-[var(--radius-1)] bg-transparent px-1 text-sm font-medium text-[var(--text-primary)] outline-none focus-visible:shadow-[var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-60"
          data-testid="global-project-selector"
          disabled={loading || Boolean(projectListError)}
          onChange={(event) => {
            if (!requestProjectSelection(event.target.value || null)) {
              event.currentTarget.value = selectedProjectId ?? "";
            }
          }}
          value={selectedProjectId ?? ""}
        >
          <option value="">全部项目</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </label>
      <p
        aria-live="polite"
        className="mt-1 text-[11px] leading-4 text-[var(--text-tertiary)]"
        id="global-project-filter-status"
      >
        {statusMessage}
      </p>
      {projectListError ? (
        <p className="mt-1 text-xs font-semibold text-[var(--state-danger)]" role="alert">
          {projectListError}
        </p>
      ) : null}
      {preferenceError ? (
        <p className="mt-1 text-xs font-semibold text-[var(--state-danger)]" role="alert">
          {preferenceError}
        </p>
      ) : null}
    </div>
  );
}
