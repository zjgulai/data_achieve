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
  it("contains the approved product entries and platform settings", () => {
    expect(primaryNavigation.map((item) => item.label)).toEqual([
      "工作台",
      "监测项目",
      "采集工作流",
      "数据资产",
      "洞察与交付",
      "能力市场",
      "系统设置",
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

  it("adds New Insight as the first child under intelligence", () => {
    const intelligence = primaryNavigation.find(
      (item) => item.href === "/intelligence",
    )!;
    expect(primaryNavigation).toHaveLength(7);
    expect(intelligence.children[0]).toEqual({
      href: "/new",
      label: "新建洞察",
    });

    const newInsight = intelligence.children[0]!;
    expect(isNavigationChildActive("/new", "", newInsight)).toBe(true);
    expect(
      isNavigationChildActive(
        "/new/0f7d9c2e-5a1b-4c3d-8e9f-1a2b3c4d5e6f",
        "",
        newInsight,
      ),
    ).toBe(true);
    expect(
      isNavigationItemActive(
        "/new/0f7d9c2e-5a1b-4c3d-8e9f-1a2b3c4d5e6f",
        "",
        intelligence,
      ),
    ).toBe(true);
    expect(isNavigationChildActive("/newish", "", newInsight)).toBe(false);
  });

  it("matches dynamic report details under the reports child", () => {
    const intelligence = primaryNavigation.find(
      (item) => item.href === "/intelligence",
    )!;
    const reports = intelligence.children.find(
      (item) => String(item.href) === "/reports",
    )!;

    expect(
      isNavigationChildActive(
        "/reports/0f7d9c2e-5a1b-4c3d-8e9f-1a2b3c4d5e6f",
        "",
        reports,
      ),
    ).toBe(true);
    expect(isNavigationChildActive("/reports-archive", "", reports)).toBe(false);
  });

  it("marks a child route through its parent", () => {
    const workflow = primaryNavigation.find(
      (item) => item.href === "/automation",
    );
    expect(workflow).toBeDefined();
    expect(isNavigationItemActive("/tasks", "", workflow!)).toBe(true);
  });

  it("adds the two planner modes under the workflow entry", () => {
    const workflow = primaryNavigation.find(
      (item) => item.href === "/automation",
    );
    expect(workflow?.children).toEqual(
      expect.arrayContaining([
        {
          href: "/automation/planner?mode=periodic_monitoring",
          label: "创建监测项目",
        },
        {
          href: "/automation/planner?mode=batch_research",
          label: "批量检索与解析",
        },
      ]),
    );
  });

  it("adds Saved Plans under workflow and keeps dynamic Plan details in that parent", () => {
    const workflow = primaryNavigation.find(
      (item) => item.href === "/automation",
    );

    expect(workflow?.children).toEqual(
      expect.arrayContaining([
        {
          href: "/automation/plans",
          label: "已保存计划",
        },
        {
          href: "/automation/runs",
          label: "运行记录",
        },
      ]),
    );
    expect(
      isNavigationItemActive(
        "/automation/projects/project-a/plans/plan-a",
        "",
        workflow!,
      ),
    ).toBe(true);
  });

  it("uses the planner mode query to activate exactly one workflow child", () => {
    const workflow = primaryNavigation.find(
      (item) => item.href === "/automation",
    )!;
    const periodic = workflow.children.find(
      (item) =>
        String(item.href) === "/automation/planner?mode=periodic_monitoring",
    )!;
    const batch = workflow.children.find(
      (item) => String(item.href) === "/automation/planner?mode=batch_research",
    )!;

    expect(
      isNavigationChildActive(
        "/automation/planner",
        "mode=periodic_monitoring",
        periodic,
      ),
    ).toBe(true);
    expect(
      isNavigationChildActive(
        "/automation/planner",
        "mode=periodic_monitoring",
        batch,
      ),
    ).toBe(false);
    expect(
      isNavigationChildActive(
        "/automation/planner",
        "mode=batch_research",
        batch,
      ),
    ).toBe(true);
    expect(
      isNavigationChildActive(
        "/automation/planner",
        "mode=batch_research",
        periodic,
      ),
    ).toBe(false);
    expect(isNavigationChildActive("/automation/planner", "", periodic)).toBe(
      false,
    );
    expect(
      isNavigationItemActive(
        "/automation/planner",
        "mode=batch_research",
        workflow,
      ),
    ).toBe(true);
    expect(isNavigationItemActive("/automation", "", workflow)).toBe(true);
  });

  it("does not mark unrelated routes active", () => {
    expect(
      isNavigationItemActive("/api-market", "", primaryNavigation[0]!),
    ).toBe(false);
  });

  it("uses query values to highlight exactly one capability child", () => {
    const market = primaryNavigation.find(
      (item) => item.href === "/api-market",
    )!;
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

  it("keeps Discovery nested under API Market without adding a primary item", () => {
    const market = primaryNavigation.find(
      (item) => item.href === "/api-market",
    )!;
    const discovery = market.children.find(
      (item) => String(item.href) === "/api-market/discovery",
    );

    expect(primaryNavigation).toHaveLength(7);
    expect(discovery).toEqual({
      href: "/api-market/discovery",
      label: "能力发现 Preview",
    });
    expect(
      isNavigationChildActive("/api-market/discovery", "", discovery!),
    ).toBe(true);
    expect(isNavigationItemActive("/api-market/discovery", "", market)).toBe(
      true,
    );
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
