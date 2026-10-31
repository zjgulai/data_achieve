import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { CONSOLE_URL, resolveAppUrl } from "@/lib/app-links";

describe("app links", () => {
  it("defaults the console URL to the site root", () => {
    expect(resolveAppUrl(undefined, "/")).toBe("/");
    expect(resolveAppUrl("", "/")).toBe("/");
    expect(resolveAppUrl("   ", "/")).toBe("/");
  });

  it("accepts an absolute override and strips trailing slashes", () => {
    expect(resolveAppUrl("http://localhost:3001", "/")).toBe(
      "http://localhost:3001",
    );
    expect(resolveAppUrl("https://scrapy.example.com/", "/")).toBe(
      "https://scrapy.example.com",
    );
  });

  it("preserves the site root", () => {
    expect(resolveAppUrl("/", "/insight")).toBe("/");
    expect(resolveAppUrl("/insight/", "/insight")).toBe("/insight");
  });

  it("exports a usable href", () => {
    expect(CONSOLE_URL).toMatch(/^(?:\/|https?:\/\/)/);
  });

  it("the navigation renders the shared cross-app link", () => {
    const sidebar = read("../../src/components/layout/sidebar.tsx");
    const drawer = read("../../src/components/layout/mobile-navigation.tsx");
    const link = read("../../src/components/layout/app-switch-link.tsx");

    expect(sidebar).toContain("<AppSwitchLink />");
    expect(drawer).toContain("<AppSwitchLink onNavigate={close} />");
    expect(link).toContain('from "@/lib/app-links"');
    expect(link).toContain("href={CONSOLE_URL}");
    // 跨应用链接是站点根，不能经过 next/link 的 basePath 换算。
    expect(link).not.toContain('from "next/link"');
    expect(link).not.toContain("/insight");
  });
});

function read(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");
}
