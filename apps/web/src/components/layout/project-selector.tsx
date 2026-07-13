"use client";

import { usePathname } from "next/navigation";

import { useProjectSelection } from "@/components/layout/project-selection-provider";
import {
  projectFilterStatusMessage,
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

  return (
    <div
      className="min-w-0 rounded-xl border border-[#EDE6DF] bg-[#FBF8F5] px-3 py-2"
      data-project-filter-applied={String(filterApplied)}
      data-route-project-id={routeProjectId ?? undefined}
    >
      <label className="flex min-w-0 items-center gap-2 text-xs font-semibold text-[#5F5757]">
        <span className="shrink-0">{routeProjectId ? "项目偏好" : "项目"}</span>
        <select
          aria-describedby="global-project-filter-status"
          className="min-w-0 max-w-48 bg-transparent text-sm font-medium text-[#2E201C] outline-none disabled:cursor-not-allowed disabled:opacity-60"
          data-testid="global-project-selector"
          disabled={loading || Boolean(projectListError)}
          onChange={(event) => selectProject(event.target.value || null)}
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
        className="mt-1 text-[11px] leading-4 text-[#8B7770]"
        id="global-project-filter-status"
      >
        {statusMessage}
      </p>
      {projectListError ? (
        <p className="mt-1 text-xs font-semibold text-[#B85F4F]" role="alert">
          {projectListError}
        </p>
      ) : null}
      {preferenceError ? (
        <p className="mt-1 text-xs font-semibold text-[#B85F4F]" role="alert">
          {preferenceError}
        </p>
      ) : null}
    </div>
  );
}
