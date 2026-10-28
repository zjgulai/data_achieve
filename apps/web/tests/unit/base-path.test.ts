import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * base-path 的两个换算方向都要在「有前缀」和「无前缀」两种部署下成立。
 *
 * 无前缀是本地与 E2E 的形态，有前缀是生产 /insight 的形态。
 * 因为 BASE_PATH 是模块加载时读的构建期常量，每个场景都要重新导入模块。
 */
async function loadModule(basePath: string) {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_BASE_PATH", basePath);
  return import("@/lib/base-path");
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("base path without a prefix", () => {
  it("passes paths through unchanged in both directions", async () => {
    const { BASE_PATH, stripBasePath, withBasePath } = await loadModule("");

    expect(BASE_PATH).toBe("");
    expect(stripBasePath("/reports/report-a")).toBe("/reports/report-a");
    expect(withBasePath("/reports/report-a")).toBe("/reports/report-a");
    // 根路径不能变成空串，否则 history.replaceState 会拿到非法 URL。
    expect(withBasePath("/")).toBe("/");
  });
});

describe("base path with /insight", () => {
  it("strips only the prefix and keeps the rest of the route", async () => {
    const { stripBasePath } = await loadModule("/insight");

    expect(stripBasePath("/insight/reports/report-a")).toBe("/reports/report-a");
    expect(stripBasePath("/insight")).toBe("/");
    // 无前缀路径原样返回：调用方可能已经换算过一次。
    expect(stripBasePath("/reports/report-a")).toBe("/reports/report-a");
  });

  it("adds the prefix exactly once", async () => {
    const { withBasePath } = await loadModule("/insight");

    expect(withBasePath("/reports/report-a")).toBe("/insight/reports/report-a");
    expect(withBasePath("/insight/reports/report-a")).toBe(
      "/insight/reports/report-a",
    );
    expect(withBasePath("/")).toBe("/insight");
    expect(withBasePath("/insight")).toBe("/insight");
  });

  it("does not confuse a sibling path that merely starts with the same letters", async () => {
    // /insights 不是 /insight 的子路径。按前缀字符串判断会误伤，
    // 这里必须走 `${BASE_PATH}/` 边界比较。
    const { stripBasePath, withBasePath } = await loadModule("/insight");

    expect(stripBasePath("/insights")).toBe("/insights");
    expect(withBasePath("/insights")).toBe("/insight/insights");
  });
});
