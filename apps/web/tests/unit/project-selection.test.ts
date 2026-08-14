// @vitest-environment jsdom

import * as React from "react";
import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ProjectSelectionProvider,
  type ProjectSelectionContextValue,
  useProjectSelection,
} from "@/components/layout/project-selection-provider";
import { listProjects } from "@/lib/api/projects";
import {
  projectFilterStatusMessage,
  isProjectFilterApplied,
  projectSelectionEventName,
  resolveRouteScopedProjectId,
  resolveAppliedProjectId,
  selectedProjectStorageKey,
  writeSelectedProjectId,
} from "@/lib/project-selection";
import type { Project } from "@/types/project";

vi.mock("next/navigation", () => ({
  usePathname: () => "/automation/planner",
}));

vi.mock("@/lib/api/projects", () => ({
  listProjects: vi.fn(),
}));

const listProjectsMock = vi.mocked(listProjects);
vi.stubGlobal("React", React);
(
  globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

function ProjectSelectionProbe({
  onValue,
}: {
  onValue: (value: ProjectSelectionContextValue) => void;
}) {
  const value = useProjectSelection();
  React.useEffect(() => {
    onValue(value);
  }, [onValue, value]);
  return null;
}

describe("shared project selection", () => {
  it("reuses the existing same-tab event name", () => {
    expect(projectSelectionEventName).toBe(
      "data-intelligence-hub:project-selection",
    );
  });

  it("marks filtering only for the matching successful planner project", () => {
    expect(
      isProjectFilterApplied({
        pathname: "/automation/planner",
        selectedProjectId: "project-a",
        appliedProjectId: "project-a",
      }),
    ).toBe(true);
    expect(
      isProjectFilterApplied({
        pathname: "/dashboard",
        selectedProjectId: "project-a",
        appliedProjectId: "project-a",
      }),
    ).toBe(false);
    expect(
      isProjectFilterApplied({
        pathname: "/automation/planner",
        selectedProjectId: "project-a",
        appliedProjectId: "project-b",
      }),
    ).toBe(false);
    expect(
      isProjectFilterApplied({
        pathname: "/automation/planner",
        selectedProjectId: null,
        appliedProjectId: null,
      }),
    ).toBe(false);

    expect(
      isProjectFilterApplied({
        pathname: "/automation/plans",
        selectedProjectId: "project-a",
        appliedProjectId: "project-a",
      }),
    ).toBe(true);
  });

  it("describes dynamic Plan detail as URL Project-scoped without applying the global preference", () => {
    const pathname = "/automation/projects/project-a/plans/plan-a";

    expect(resolveRouteScopedProjectId(pathname)).toBe("project-a");
    expect(
      projectFilterStatusMessage({
        pathname,
        selectedProjectId: "project-b",
        filterApplied: false,
      }),
    ).toBe(
      "当前页面按 URL Project project-a 读取；顶部项目偏好 project-b 不影响本页",
    );
    expect(
      isProjectFilterApplied({
        pathname,
        selectedProjectId: "project-b",
        appliedProjectId: null,
      }),
    ).toBe(false);
  });

  it("keeps archived URL Project context visible when it is not selectable globally", () => {
    const pathname = "/automation/projects/archived%20project/plans/plan-a";

    expect(resolveRouteScopedProjectId(pathname)).toBe("archived project");
    expect(
      projectFilterStatusMessage({
        pathname,
        selectedProjectId: null,
        filterApplied: false,
      }),
    ).toBe(
      "当前页面按 URL Project archived project 读取；顶部项目偏好不影响本页",
    );
  });

  it("rejects stale or inactive Preview bindings", () => {
    const projects = [
      { id: "project-a", status: "active" },
      { id: "project-b", status: "active" },
      { id: "project-c", status: "archived" },
    ] as Project[];

    expect(resolveAppliedProjectId(projects, "project-a", "project-a")).toBe(
      "project-a",
    );
    expect(
      resolveAppliedProjectId(projects, "project-a", "project-b"),
    ).toBeNull();
    expect(
      resolveAppliedProjectId(projects, "project-a", "project-c"),
    ).toBeNull();
    expect(resolveAppliedProjectId(projects, null, "project-a")).toBeNull();
  });

  it("keeps the stored preference when the active Project list is unavailable", async () => {
    const storedProjectId = "project-a";
    window.localStorage.setItem(selectedProjectStorageKey, storedProjectId);
    listProjectsMock.mockRejectedValueOnce(
      new Error("project list unavailable"),
    );
    const addEventListener = vi.spyOn(window, "addEventListener");
    const removeEventListener = vi.spyOn(window, "removeEventListener");
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        createElement(ProjectSelectionProvider, null, createElement("span")),
      );
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(listProjectsMock).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(selectedProjectStorageKey)).toBe(
      storedProjectId,
    );

    act(() => {
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: selectedProjectStorageKey,
          newValue: storedProjectId,
        }),
      );
    });
    const storedAfterEvent = window.localStorage.getItem(
      selectedProjectStorageKey,
    );
    const selectionListener = addEventListener.mock.calls.find(
      ([eventName]) => eventName === projectSelectionEventName,
    )?.[1];
    const storageListener = addEventListener.mock.calls.find(
      ([eventName]) => eventName === "storage",
    )?.[1];

    await act(async () => {
      root.unmount();
    });
    container.remove();

    expect(storedAfterEvent).toBe(storedProjectId);
    expect(removeEventListener).toHaveBeenCalledWith(
      projectSelectionEventName,
      selectionListener,
    );
    expect(removeEventListener).toHaveBeenCalledWith(
      "storage",
      storageListener,
    );
  });

  it("clears a stale preference error after a valid synchronized selection", async () => {
    const projectId = "project-a";
    const projects = [{ id: projectId, status: "active" }] as Project[];
    listProjectsMock.mockResolvedValueOnce(projects);
    vi.spyOn(Storage.prototype, "getItem").mockImplementationOnce(() => {
      throw new Error("transient storage read failure");
    });
    const values: ProjectSelectionContextValue[] = [];
    const onValue = (value: ProjectSelectionContextValue) => {
      values.push(value);
    };
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        createElement(
          ProjectSelectionProvider,
          null,
          createElement(ProjectSelectionProbe, { onValue }),
        ),
      );
      await Promise.resolve();
      await Promise.resolve();
    });
    const initialPreferenceError = values.at(-1)?.preferenceError;

    let persisted = false;
    act(() => {
      persisted = writeSelectedProjectId(projectId);
    });
    const synchronizedValue = values.at(-1);

    await act(async () => {
      root.unmount();
    });
    container.remove();

    expect(initialPreferenceError).toBe("项目偏好暂不可用；当前选择未保存");
    expect(persisted).toBe(true);
    expect(synchronizedValue?.selectedProjectId).toBe(projectId);
    expect(synchronizedValue?.preferenceError).toBeNull();
  });
});

afterEach(() => {
  listProjectsMock.mockReset();
  window.localStorage.clear();
  document.body.replaceChildren();
  vi.restoreAllMocks();
});
