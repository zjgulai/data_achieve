"use client";

import { usePathname } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { listProjects } from "@/lib/api/projects";
import {
  isProjectFilterApplied,
  projectSelectionEventName,
  readSelectedProjectPreference,
  resolveAppliedProjectId,
  resolveSelectedProjectId,
  selectedProjectStorageKey,
  writeSelectedProjectId,
} from "@/lib/project-selection";
import type { Project } from "@/types/project";

const projectListUnavailableMessage = "项目列表暂不可用";
const projectPreferenceUnavailableMessage =
  "项目偏好暂不可用；当前选择未保存";

type ProjectBinding = {
  selectedProjectId: string | null;
  appliedProjectId: string | null;
};

export type ProjectSelectionContextValue = {
  projects: Project[];
  selectedProject: Project | null;
  selectedProjectId: string | null;
  loading: boolean;
  projectListError: string | null;
  preferenceError: string | null;
  filterApplied: boolean;
  selectProject: (projectId: string | null) => void;
  markProjectFilterApplied: (projectId: string) => void;
  clearProjectFilterApplied: () => void;
};

const ProjectSelectionContext =
  createContext<ProjectSelectionContextValue | null>(null);

function eventProjectId(event: Event): string | null {
  const detail = (event as CustomEvent<{ projectId?: unknown }>).detail;
  return typeof detail?.projectId === "string" && detail.projectId
    ? detail.projectId
    : null;
}

export function ProjectSelectionProvider({
  children,
}: {
  children: React.ReactNode;
}): React.ReactNode {
  const pathname = usePathname();
  const [projects, setProjects] = useState<Project[]>([]);
  const [binding, setBinding] = useState<ProjectBinding>({
    selectedProjectId: null,
    appliedProjectId: null,
  });
  const [loading, setLoading] = useState(true);
  const [projectListError, setProjectListError] = useState<string | null>(null);
  const [preferenceError, setPreferenceError] = useState<string | null>(null);
  const activeProjectsRef = useRef<Project[]>([]);
  const projectsValidatedRef = useRef(false);
  const projectRequestRef = useRef<Promise<Project[]> | null>(null);
  const requestedProjectIdRef = useRef<string | null>(null);

  const applyRequestedSelection = useCallback(
    (projectId: string | null, correctInvalidPreference = false) => {
      requestedProjectIdRef.current = projectId;
      if (!projectsValidatedRef.current) {
        return;
      }
      const resolved = resolveSelectedProjectId(
        activeProjectsRef.current,
        projectId,
      );
      setBinding((current) =>
        current.selectedProjectId === resolved
          ? current
          : { selectedProjectId: resolved, appliedProjectId: null },
      );
      if (correctInvalidPreference) {
        setPreferenceError(
          projectId === resolved || writeSelectedProjectId(resolved)
            ? null
            : projectPreferenceUnavailableMessage,
        );
      }
    },
    [],
  );

  const selectProject = useCallback(
    (projectId: string | null) => {
      if (!projectsValidatedRef.current) {
        requestedProjectIdRef.current = projectId;
        return;
      }
      const resolved = resolveSelectedProjectId(
        activeProjectsRef.current,
        projectId,
      );
      applyRequestedSelection(resolved);
      setPreferenceError(
        writeSelectedProjectId(resolved)
          ? null
          : projectPreferenceUnavailableMessage,
      );
    },
    [applyRequestedSelection],
  );

  const markProjectFilterApplied = useCallback((projectId: string) => {
    setBinding((current) => {
      const resolved = resolveAppliedProjectId(
        activeProjectsRef.current,
        current.selectedProjectId,
        projectId,
      );
      return current.appliedProjectId === resolved
        ? current
        : { ...current, appliedProjectId: resolved };
    });
  }, []);

  const clearProjectFilterApplied = useCallback(() => {
    setBinding((current) =>
      current.appliedProjectId === null
        ? current
        : { ...current, appliedProjectId: null },
    );
  }, []);

  useEffect(() => {
    let cancelled = false;
    const preference = readSelectedProjectPreference();
    requestedProjectIdRef.current = preference.value;
    setPreferenceError(
      preference.available ? null : projectPreferenceUnavailableMessage,
    );

    function onProjectSelection(event: Event) {
      applyRequestedSelection(eventProjectId(event), true);
    }

    function onStorage(event: StorageEvent) {
      if (event.key === selectedProjectStorageKey) {
        applyRequestedSelection(event.newValue, true);
      }
    }

    window.addEventListener(projectSelectionEventName, onProjectSelection);
    window.addEventListener("storage", onStorage);

    const projectRequest = projectRequestRef.current ?? listProjects();
    projectRequestRef.current = projectRequest;
    projectRequest
      .then((items) => {
        if (cancelled) {
          return;
        }
        const activeProjects = items.filter(
          (project) => project.status === "active",
        );
        activeProjectsRef.current = activeProjects;
        projectsValidatedRef.current = true;
        const requestedProjectId = requestedProjectIdRef.current;
        const resolved = resolveSelectedProjectId(
          activeProjects,
          requestedProjectId,
        );
        setProjects(activeProjects);
        setBinding({ selectedProjectId: resolved, appliedProjectId: null });
        setProjectListError(null);
        setLoading(false);

        if (requestedProjectId !== resolved) {
          setPreferenceError(
            writeSelectedProjectId(resolved)
              ? null
              : projectPreferenceUnavailableMessage,
          );
        }
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        activeProjectsRef.current = [];
        projectsValidatedRef.current = false;
        setProjects([]);
        setBinding({ selectedProjectId: null, appliedProjectId: null });
        setProjectListError(projectListUnavailableMessage);
        setLoading(false);
      });

    return () => {
      cancelled = true;
      projectsValidatedRef.current = false;
      window.removeEventListener(projectSelectionEventName, onProjectSelection);
      window.removeEventListener("storage", onStorage);
    };
  }, [applyRequestedSelection]);

  useEffect(() => {
    clearProjectFilterApplied();
  }, [clearProjectFilterApplied, pathname]);

  const selectedProject = useMemo(
    () =>
      projects.find((project) => project.id === binding.selectedProjectId) ??
      null,
    [binding.selectedProjectId, projects],
  );
  const filterApplied = isProjectFilterApplied({
    pathname,
    selectedProjectId: binding.selectedProjectId,
    appliedProjectId: binding.appliedProjectId,
  });
  const value = useMemo<ProjectSelectionContextValue>(
    () => ({
      projects,
      selectedProject,
      selectedProjectId: binding.selectedProjectId,
      loading,
      projectListError,
      preferenceError,
      filterApplied,
      selectProject,
      markProjectFilterApplied,
      clearProjectFilterApplied,
    }),
    [
      binding.selectedProjectId,
      clearProjectFilterApplied,
      filterApplied,
      loading,
      markProjectFilterApplied,
      preferenceError,
      projectListError,
      projects,
      selectProject,
      selectedProject,
    ],
  );

  return (
    <ProjectSelectionContext.Provider value={value}>
      {children}
    </ProjectSelectionContext.Provider>
  );
}

export function useProjectSelection(): ProjectSelectionContextValue {
  const value = useContext(ProjectSelectionContext);
  if (!value) {
    throw new Error(
      "useProjectSelection must be used within ProjectSelectionProvider",
    );
  }
  return value;
}
