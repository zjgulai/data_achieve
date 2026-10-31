import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

/** 读同目录下的源文件。 */
function read(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8");
}

test("the top bar mounts the mobile navigation", () => {
  const source = read("./top-bar.tsx");
  assert.equal(source.includes("MobileNavigation"), true);
});

test("the mobile drawer reuses the shared navigation sections", () => {
  const source = read("./mobile-navigation.tsx");
  // 复用侧栏的渲染组件，不另抄一份导航数据。
  assert.equal(source.includes("NavigationSections"), true);
  assert.equal(source.includes('from "@/lib/routes"'), false);
  assert.equal(source.includes("usePathname()"), true);
  assert.equal(source.includes("onNavigate={close}"), true);
});

test("the mobile opener exposes its label and expanded state", () => {
  const source = read("./mobile-navigation.tsx");
  assert.match(source, /aria-label="打开导航"/);
  assert.match(source, /aria-expanded=\{open\}/);
  assert.match(source, /aria-controls="mobile-primary-navigation"/);
  // 菜单按钮只在 <lg 显示。
  assert.match(source, /lg:hidden/);
});

test("the mobile drawer is a labelled modal", () => {
  const source = read("./mobile-navigation.tsx");
  assert.match(source, /role="dialog"/);
  assert.match(source, /aria-modal="true"/);
  assert.match(source, /aria-label="移动主导航"/);
  assert.match(source, /aria-label="关闭导航遮罩"/);
  assert.match(source, /aria-label="关闭导航"/);
});

test("the mobile drawer closes on Escape and route changes", () => {
  const source = read("./mobile-navigation.tsx");
  assert.equal(source.includes('event.key === "Escape"'), true);
  assert.equal(source.includes("[pathname]"), true);
  assert.equal(source.includes("setOpen(false)"), true);
});

test("the mobile drawer traps focus", () => {
  const source = read("./mobile-navigation.tsx");
  assert.equal(source.includes("focusableSelector"), true);
  assert.equal(source.includes('event.key !== "Tab"'), true);
  assert.equal(source.includes("first.focus()"), true);
  assert.equal(source.includes("last.focus()"), true);
});

test("the desktop sidebar hides below the lg breakpoint", () => {
  const source = read("./sidebar.tsx");
  assert.match(source, /className="hidden[^"]*lg:flex/);
});
