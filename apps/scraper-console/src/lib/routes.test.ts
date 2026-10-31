import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import {
  B5_ROUTES,
  KEPT_ROUTES,
  NEW_ROUTES,
  PRIMARY_NAVIGATION,
  ROOT_ROUTE,
  ROUTE_REDIRECTS,
  SECONDARY_NAVIGATION,
  activeNavigationHref,
  buildRedirects,
  isActiveRoute,
  navigationHrefs,
  openToolDetail,
  parametersOf,
  resolveToolDetailState,
  toolDetailHref,
} from "./routes.ts";

test("the redirect table has the seven frozen entries", () => {
  assert.equal(ROUTE_REDIRECTS.length, 7);
});

test("the old capability directory redirects to tools", () => {
  const r = ROUTE_REDIRECTS.find(x => x.source === "/platforms");
  assert.ok(r);
  assert.equal(r.destination, "/tools");
  assert.equal(r.permanent, true);
});

test("the platform package directory redirects to tools", () => {
  const r = ROUTE_REDIRECTS.find(x => x.source === "/skills");
  assert.ok(r);
  assert.equal(r.destination, "/tools");
});

test("the platform detail repoints to a tool detail", () => {
  const r = ROUTE_REDIRECTS.find(x => x.source === "/skills/:platformId");
  assert.ok(r);
  // 段名必须与 source 一致。Next.js 拒绝改名的重定向。
  assert.equal(r.destination, "/tools/:platformId");
  assert.deepEqual(parametersOf(r.destination), parametersOf(r.source));
});

test("the collector docs redirect to docs", () => {
  assert.equal(
    ROUTE_REDIRECTS.find(x => x.source === "/collector-docs")?.destination,
    "/docs"
  );
});

test("the collect result keeps its path parameter under runs", () => {
  const r = ROUTE_REDIRECTS.find(x => x.source === "/collect/:runId");
  assert.ok(r);
  assert.equal(r.destination, "/runs/:runId");
  // 段名由 snake_case 改为 camelCase。
  assert.deepEqual(parametersOf(r.source), ["runId"]);
});

test("datasets redirect to assets", () => {
  assert.equal(
    ROUTE_REDIRECTS.find(x => x.source === "/datasets")?.destination,
    "/assets"
  );
});

test("raw records redirect under assets", () => {
  assert.equal(
    ROUTE_REDIRECTS.find(x => x.source === "/raw-records")?.destination,
    "/assets/records"
  );
});

test("every redirect preserves its path parameters", () => {
  // 参数个数要一致。/skills/:platformId 目标改名为 :toolId，值仍保留。
  for (const r of ROUTE_REDIRECTS) {
    const from = parametersOf(r.source);
    const to = parametersOf(r.destination);
    assert.equal(
      to.length,
      from.length,
      `${r.source} 有 ${from.length} 个参数，目标 ${r.destination} 有 ${to.length} 个`
    );
  }
});

test("no source path collides with a destination path", () => {
  const sources = new Set(ROUTE_REDIRECTS.map(r => r.source));
  for (const r of ROUTE_REDIRECTS) {
    assert.equal(
      sources.has(r.destination),
      false,
      `${r.destination} 既是目标又是来源，会形成重定向链`
    );
  }
});

test("kept routes are not redirected", () => {
  const sources = new Set(ROUTE_REDIRECTS.map(r => r.source));
  for (const kept of KEPT_ROUTES) {
    assert.equal(sources.has(kept), false, `${kept} 保持路径，不应出现在重定向表`);
  }
});

test("the three route groups have explicit sizes", () => {
  // 三组分别断言。合并求和会掩盖分组错误。
  // B5 的 /workbench 已移到 NEW。它不再属于保持路径。
  assert.equal(
    KEPT_ROUTES.length,
    6,
    `KEPT_ROUTES 应为 6 条，实际 ${KEPT_ROUTES.length} 条`
  );
  // NEW 含 B5 的 3 条一级入口、2 条 B5 详情页与 4 条早前批次路由。
  assert.equal(
    NEW_ROUTES.length,
    9,
    `NEW_ROUTES 应为 9 条，实际 ${NEW_ROUTES.length} 条`
  );
  // 总计 = 7 条重定向 + 6 条保持 + 1 条根路由 + 9 条新增。
  assert.equal(
    ROUTE_REDIRECTS.length +
      KEPT_ROUTES.length +
      (ROOT_ROUTE ? 1 : 0) +
      NEW_ROUTES.length,
    23,
    "三组加根路由应为 23 条"
  );
});

test("the frozen table still has fourteen routes", () => {
  // 冻结表原为 15 条现有路由。B1-17 删除死页 /settings/account 后为 14 条。
  assert.equal(
    ROUTE_REDIRECTS.length + KEPT_ROUTES.length + (ROOT_ROUTE ? 1 : 0),
    14
  );
});

test("the three B5 routes share the new-route group", () => {
  // 三个路由都是 B5 新建。它们必须同组。
  assert.equal(B5_ROUTES.length, 3);
  for (const route of B5_ROUTES) {
    assert.equal(NEW_ROUTES.includes(route), true, `${route} 应属于 NEW_ROUTES`);
    assert.equal(KEPT_ROUTES.includes(route), false, `${route} 不应属于 KEPT_ROUTES`);
  }
});

test("the report center and the report reader are registered", () => {
  assert.equal(NEW_ROUTES.includes("/reports"), true);
  assert.equal(NEW_ROUTES.includes("/reports/[artifactId]"), true);
});

test("the capability directory and its deep link are registered", () => {
  assert.equal(NEW_ROUTES.includes("/capabilities"), true);
  assert.equal(NEW_ROUTES.includes("/capabilities/[toolId]"), true);
});

test("each new route has a page file", () => {
  // 声明了路由却没有页面，用户会得到 404。
  // 本测试在 2026-10-17 之前缺失，导致 /settings/providers 与
  // /settings/members 声明后长期无页面而无人发现。
  const appDir = fileURLToPath(new URL("../app/", import.meta.url));
  for (const route of NEW_ROUTES) {
    // "/tools/[toolId]" -> "tools/[toolId]/page.tsx"
    const segment = route.replace(/^\//, "");
    const file = `${appDir}${segment}/page.tsx`;
    assert.equal(existsSync(file), true, `路由 ${route} 缺少页面文件：${file}`);
  }
});

test("the root route is not itself a redirect", () => {
  // 新 IA 里 / 是真实页面，不是重定向。
  assert.equal(
    ROUTE_REDIRECTS.some(r => r.source === ROOT_ROUTE),
    false
  );
});

test("buildRedirects drops the note field", () => {
  const out = buildRedirects();
  assert.equal(out.length, ROUTE_REDIRECTS.length);
  for (const r of out) {
    assert.deepEqual(Object.keys(r).sort(), ["destination", "permanent", "source"]);
  }
});

test("every redirect is permanent", () => {
  for (const r of ROUTE_REDIRECTS) assert.equal(r.permanent, true);
});

test("each redirect states its purpose", () => {
  for (const r of ROUTE_REDIRECTS) assert.ok(r.note.length > 0, `${r.source} 缺说明`);
});

test("the primary navigation has exactly four top-level entries", () => {
  // 契约冻结：一级导航只有 4 个：工作台、报告、连接器、设置。
  assert.deepEqual(
    PRIMARY_NAVIGATION.map(section => section.name),
    ["工作台", "报告", "连接器", "设置"]
  );
});

test("the sidebar primary navigation starts at the workbench", () => {
  // UI 规格 §0.1：/workbench 是唯一任务入口。
  assert.equal(PRIMARY_NAVIGATION[0]?.name, "工作台");
  assert.equal(PRIMARY_NAVIGATION[0]?.href, "/workbench");
});

test("only workbench and reports are clickable top-level entries", () => {
  // 连接器与设置只作分组标题，不跳转。
  assert.deepEqual(
    PRIMARY_NAVIGATION.filter(section => section.href !== undefined).map(
      section => section.href
    ),
    ["/workbench", "/reports"]
  );
  assert.equal(PRIMARY_NAVIGATION[2]?.href, undefined);
  assert.equal(PRIMARY_NAVIGATION[3]?.href, undefined);
});

test("the workbench groups its drill-down pages", () => {
  const workbench = PRIMARY_NAVIGATION[0];
  assert.ok(workbench);
  assert.deepEqual(
    workbench.groups?.map(group => group.name),
    ["监测与采集", "数据与资产"]
  );
  const hrefs =
    workbench.groups?.flatMap(group => group.items.map(item => item.href)) ?? [];
  assert.deepEqual(hrefs, [
    "/projects",
    "/tasks",
    "/monitors",
    "/runs",
    "/assets",
    "/assets/records",
    "/abi",
  ]);
});

test("projects, runs and assets are not primary entries", () => {
  // 契约明令禁止把这三个做成一级导航。它们是工作台的下钻。
  const primaryHrefs = PRIMARY_NAVIGATION.flatMap(section =>
    section.href ? [section.href] : []
  );
  const allHrefs = navigationHrefs(PRIMARY_NAVIGATION);
  for (const route of ["/projects", "/runs", "/assets"]) {
    assert.equal(primaryHrefs.includes(route), false, `${route} 不得作为一级入口`);
    assert.equal(allHrefs.includes(route), true, `${route} 应保留为二级入口`);
  }
});

test("the sidebar links the three B5 pages", () => {
  const hrefs = navigationHrefs(PRIMARY_NAVIGATION);
  for (const route of B5_ROUTES) {
    assert.equal(hrefs.includes(route), true, `导航缺少 ${route}`);
  }
});

test("the dashboard is not a primary entry", () => {
  assert.equal(
    PRIMARY_NAVIGATION.some(section => section.href === "/dashboard"),
    false,
    "/dashboard 不得作为一级入口"
  );
  // 页面保留。入口在「设置」分组下。
  assert.equal(
    navigationHrefs(SECONDARY_NAVIGATION).includes("/dashboard"),
    true,
    "/dashboard 页面保留，应出现在设置分组"
  );
});

test("the settings section reuses the secondary navigation", () => {
  // 旧的辅助导航列表并入「设置」一级项，不另抄一份。
  assert.equal(SECONDARY_NAVIGATION.length, 1);
  const settings = PRIMARY_NAVIGATION.find(section => section.name === "设置");
  assert.ok(settings);
  assert.deepEqual(settings, SECONDARY_NAVIGATION[0]);
  assert.deepEqual(
    settings.items?.map(item => item.name),
    ["用量与成本", "凭证", "提供方状态", "成员与工作区", "旧版概览"]
  );
});

test("the sidebar renders the shared navigation config", () => {
  // 导航数据在 routes.ts。侧栏与移动抽屉共用 NavigationSections，不能另抄一份。
  const sidebarFile = fileURLToPath(
    new URL("../components/layout/sidebar.tsx", import.meta.url)
  );
  const sidebar = readFileSync(sidebarFile, "utf8");
  assert.equal(sidebar.includes("NavigationSections"), true);
  assert.equal(sidebar.includes("usePathname()"), true);
  // 旧的「工作台 → /dashboard」硬编码必须消失。
  assert.equal(
    /name:\s*"工作台",\s*href:\s*"\/dashboard"/.test(sidebar),
    false,
    "工作台不得再指向 /dashboard"
  );

  const menuFile = fileURLToPath(
    new URL("../components/layout/navigation-sections.tsx", import.meta.url)
  );
  const menu = readFileSync(menuFile, "utf8");
  assert.equal(menu.includes("PRIMARY_NAVIGATION.map"), true);
  assert.equal(menu.includes("navigationHrefs(PRIMARY_NAVIGATION)"), true);
  assert.equal(menu.includes("section.groups"), true);
  assert.equal(menu.includes("section.items"), true);
});

test("a deep capability link highlights the capability entry", () => {
  // /capabilities/[toolId] 时父项高亮。
  assert.equal(isActiveRoute("/capabilities/exa_search", "/capabilities"), true);
  // 相邻路径不得误判。
  assert.equal(isActiveRoute("/capabilities-archive", "/capabilities"), false);
  const hrefs = navigationHrefs(PRIMARY_NAVIGATION);
  assert.equal(activeNavigationHref("/capabilities/exa_search", hrefs), "/capabilities");
  assert.equal(activeNavigationHref("/capabilities", hrefs), "/capabilities");
  assert.equal(activeNavigationHref("/workbench", hrefs), "/workbench");
  // 更具体的路径只高亮最长匹配。工具有子页时二者不再同时高亮。
  assert.equal(activeNavigationHref("/tools/tiktok", hrefs), "/tools/tiktok");
  assert.equal(activeNavigationHref("/tools", hrefs), "/tools");
  // 资产页的子路径只高亮「原始记录」。
  assert.equal(activeNavigationHref("/assets/records", hrefs), "/assets/records");
  assert.equal(activeNavigationHref("/assets/records/123", hrefs), "/assets/records");
  assert.equal(activeNavigationHref("/unknown", hrefs), null);
});

test("the tool detail link encodes the tool id", () => {
  assert.equal(toolDetailHref("exa_search"), "/capabilities/exa_search");
  // 工具标识可能含斜杠。斜杠必须编码，否则会多出一段路径。
  assert.equal(toolDetailHref("provider/tool"), "/capabilities/provider%2Ftool");
});

test("a capability list row pushes the deep link", () => {
  // 用 router.push 的替身断言跳转目标。
  const pushed: string[] = [];
  const router = {
    push: (href: string) => {
      pushed.push(href);
    },
  };
  openToolDetail(router, "exa_search");
  assert.deepEqual(pushed, ["/capabilities/exa_search"]);
});

test("the capability list row uses the deep link opener", () => {
  const file = fileURLToPath(
    new URL("../app/capabilities/page.tsx", import.meta.url)
  );
  const source = readFileSync(file, "utf8");
  assert.equal(
    source.includes("openToolDetail(router"),
    true,
    "列表行必须调用 openToolDetail"
  );
  // 抽屉已删除。列表不再自己打开详情。
  assert.equal(source.includes("ToolDetailDrawer"), false);
});

test("the tool detail state treats 404 as a missing tool", () => {
  assert.equal(
    resolveToolDetailState({ isLoading: true, error: null, hasTool: false }),
    "loading"
  );
  assert.equal(
    resolveToolDetailState({ isLoading: false, error: { status: 404 }, hasTool: false }),
    "not-found"
  );
  assert.equal(
    resolveToolDetailState({ isLoading: false, error: { status: 500 }, hasTool: false }),
    "error"
  );
  assert.equal(
    resolveToolDetailState({ isLoading: false, error: null, hasTool: true }),
    "ready"
  );
  // 没有数据也没有错误时也按不存在处理。不得显示空白页。
  assert.equal(
    resolveToolDetailState({ isLoading: false, error: null, hasTool: false }),
    "not-found"
  );
});

test("the capability detail page renders a missing-tool state", () => {
  const file = fileURLToPath(
    new URL("../app/capabilities/[toolId]/page.tsx", import.meta.url)
  );
  const source = readFileSync(file, "utf8");
  assert.equal(
    source.includes("工具不存在"),
    true,
    "404 分支必须显示「工具不存在」"
  );
  assert.equal(
    source.includes("fetchTool"),
    true,
    "详情页必须调用 GET /api/tools/{tool_id}"
  );
  assert.equal(
    source.includes('href="/capabilities"'),
    true,
    "详情页必须有返回列表的链接"
  );
});
