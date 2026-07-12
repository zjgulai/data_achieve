import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isNavigationChildActive,
  isNavigationItemActive,
  primaryNavigation,
} from "@/components/layout/navigation";
import {
  readSelectedProjectId,
  resolveSelectedProjectId,
  writeSelectedProjectId,
} from "@/lib/project-selection";
import type { Project } from "@/types/project";

describe("primary navigation", () => {
  it("contains exactly the six approved entries", () => {
    expect(primaryNavigation.map((item) => item.label)).toEqual([
      "工作台",
      "监测项目",
      "采集工作流",
      "数据资产",
      "洞察与交付",
      "能力市场",
    ]);
  });

  it("keeps legacy pages as secondary links", () => {
    const secondaryHrefs = primaryNavigation.flatMap((item) =>
      item.children.map((child) => child.href),
    );
    expect(secondaryHrefs).toEqual(
      expect.arrayContaining([
        "/tasks",
        "/sources",
        "/raw-records",
        "/entities",
        "/signals",
        "/reports",
        "/alerts",
        "/notifications",
        "/toolkit",
        "/domain/osint",
        "/domain/ecommerce",
        "/domain/social",
        "/domain/competitor",
        "/domain/agent",
        "/domain/platform",
        "/domain/governance",
      ]),
    );
  });

  it("marks a child route through its parent", () => {
    const workflow = primaryNavigation.find(
      (item) => item.href === "/automation",
    );
    expect(workflow).toBeDefined();
    expect(isNavigationItemActive("/tasks", "", workflow!)).toBe(true);
  });

  it("does not mark unrelated routes active", () => {
    expect(
      isNavigationItemActive("/api-market", "", primaryNavigation[0]!),
    ).toBe(false);
  });

  it("uses query values to highlight exactly one capability child", () => {
    const market = primaryNavigation.find((item) => item.href === "/api-market")!;
    const [scenarios, matrix, list] = market.children;
    expect(isNavigationChildActive("/api-market", "view=matrix", matrix!)).toBe(
      true,
    );
    expect(
      isNavigationChildActive("/api-market", "view=matrix", scenarios!),
    ).toBe(false);
    expect(isNavigationChildActive("/api-market", "view=matrix", list!)).toBe(
      false,
    );
    expect(isNavigationChildActive("/api-market", "", scenarios!)).toBe(true);
  });
});

describe("project selection", () => {
  const projects = [
    { id: "active", name: "Active", status: "active" },
    { id: "archived", name: "Archived", status: "archived" },
  ] as Project[];

  it("keeps only an existing active selection", () => {
    expect(resolveSelectedProjectId(projects, "active")).toBe("active");
  });

  it("falls back to all projects for archived or missing ids", () => {
    expect(resolveSelectedProjectId(projects, "archived")).toBeNull();
    expect(resolveSelectedProjectId(projects, "missing")).toBeNull();
    expect(resolveSelectedProjectId(projects, null)).toBeNull();
  });

  it("fails closed when browser storage is unavailable", () => {
    const storageError = new Error("storage unavailable");
    const dispatchEvent = vi.fn();
    vi.stubGlobal("window", {
      dispatchEvent,
      localStorage: {
        getItem: vi.fn(() => {
          throw storageError;
        }),
        removeItem: vi.fn(() => {
          throw storageError;
        }),
        setItem: vi.fn(() => {
          throw storageError;
        }),
      },
    });

    expect(readSelectedProjectId()).toBeNull();
    expect(writeSelectedProjectId("active")).toBe(false);
    expect(writeSelectedProjectId(null)).toBe(false);
    expect(dispatchEvent).not.toHaveBeenCalled();
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});
