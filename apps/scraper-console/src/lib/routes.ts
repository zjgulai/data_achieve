/**
 * 路由登记表。
 *
 * 重定向部分来自 docs/architecture/【技术方案】DIH整站能力整合方案.md §4.3。
 * 该表在 P0 冻结。改动需产品确认。
 *
 * 本模块同时保存侧栏导航与路径构造。
 * 这里不依赖 React。Node 测试可以直接加载。
 */

/** 一条重定向。 */
export type RouteRedirect = {
  /** 旧路径。含 :param 时表示保留该段。 */
  source: string;
  /** 新路径。参数名须与 source 一致。 */
  destination: string;
  /** 是否为永久重定向。 */
  permanent: boolean;
  /** 该路由的用途。供文档引用。 */
  note: string;
};

/** 段名前缀。用于识别保留参数。 */
const PARAM_PREFIX = ":";

/** 取路径里的参数名。 */
export function parametersOf(path: string): string[] {
  return path
    .split("/")
    .filter(segment => segment.startsWith(PARAM_PREFIX))
    .map(segment => segment.slice(PARAM_PREFIX.length));
}

/**
 * 冻结的重定向表。
 *
 * 顺序无关。Next.js 按 source 的精确度匹配。
 */
export const ROUTE_REDIRECTS: readonly RouteRedirect[] = [
  {
    source: "/platforms",
    destination: "/tools",
    permanent: true,
    note: "能力目录改名。筛选状态已由批次 2 写入 URL。",
  },
  {
    source: "/skills",
    destination: "/tools",
    permanent: true,
    note: "平台包目录并入能力目录。",
  },
  {
    // 段名必须与 source 一致。Next.js 不允许在重定向里改名。
    // /tools/:platformId 产生的 URL 会正常匹配 [toolId] 路由。
    source: "/skills/:platformId",
    destination: "/tools/:platformId",
    permanent: true,
    note: "平台详情改名。保留路径参数。",
  },
  {
    source: "/collector-docs",
    destination: "/docs",
    permanent: true,
    note: "采集文档改名。",
  },
  {
    source: "/collect/:runId",
    destination: "/runs/:runId",
    permanent: true,
    note: "采集结果改挂到运行下。保留路径参数。",
  },
  {
    source: "/datasets",
    destination: "/assets",
    permanent: true,
    note: "数据集归入资产域。",
  },
  {
    source: "/raw-records",
    destination: "/assets/records",
    permanent: true,
    note: "原始记录归入资产域。",
  },
];

/**
 * 保持路径的条目。仅记录，不产生重定向。
 *
 * 本组只含冻结表里的既有路由。
 * B5 新建的 /workbench 不在其中。它属于新增。
 */
export const KEPT_ROUTES: readonly string[] = [
  "/projects",
  "/projects/[id]",
  "/tasks",
  "/runs",
  "/dashboard",
  "/settings/credentials",
];

/**
 * 根路由。
 *
 * 路径不变，用途改变。原先是重定向到 /platforms。
 * 新 IA 里它是公开首页。故不属重定向，也不属纯保持。
 */
export const ROOT_ROUTE = "/";

/**
 * 本批次新增的路由。
 *
 * B5 的 /workbench、/reports 与 /capabilities 都在这里。
 * 三者都是新增，不是保持。
 */
export const NEW_ROUTES: readonly string[] = [
  // B5 工作台。唯一任务入口。见 UI 规格 §0.1。
  "/workbench",
  // B5 报告中心与阅读页。见 apps/scraper-console/src/app/reports/。
  "/reports",
  "/reports/[artifactId]",
  // B5 能力目录与详情深链。
  "/capabilities",
  "/capabilities/[toolId]",
  // 早前批次的新增路由。
  "/connect",
  "/tools/[toolId]",
  "/settings/providers",
  "/settings/members",
];

/**
 * B5 新建的三个一级入口。
 *
 * 三个路由同属一批。测试按这一组断言分组。
 */
export const B5_ROUTES: readonly string[] = [
  "/workbench",
  "/reports",
  "/capabilities",
];

/**
 * 生成 Next.js 的 redirects 配置。
 *
 * 不设 has/missing 条件。旧路径一律重定向。
 */
export function buildRedirects(): {
  source: string;
  destination: string;
  permanent: boolean;
}[] {
  return ROUTE_REDIRECTS.map(({ source, destination, permanent }) => ({
    source,
    destination,
    permanent,
  }));
}

/** 侧栏导航项。 */
export type NavigationItem = {
  /** 显示文字。 */
  readonly name: string;
  /** 目标路径。 */
  readonly href: string;
};

/**
 * 侧栏一级导航。
 *
 * UI 规格 §0.1：/workbench 是唯一任务入口。
 * /dashboard 不得作为一级入口。
 * 项目列表仍在一级导航，但它不是任务入口。
 * 图标不在这里。图标是视图层的事。
 */
export const PRIMARY_NAVIGATION: readonly NavigationItem[] = [
  { name: "工作台", href: "/workbench" },
  { name: "能力目录", href: "/capabilities" },
  { name: "报告", href: "/reports" },
  { name: "运行记录", href: "/runs" },
  { name: "工具", href: "/tools" },
  { name: "TikTok 工作台", href: "/tools/tiktok" },
  { name: "项目", href: "/projects" },
  { name: "任务", href: "/tasks" },
  { name: "资产", href: "/assets" },
  { name: "接入", href: "/connect" },
  { name: "文档", href: "/docs" },
];

/**
 * 侧栏二级导航。
 *
 * /dashboard 页面保留，入口降到这里。
 * 它不再是「工作台」，也不再是一级入口。
 */
export const SECONDARY_NAVIGATION: readonly NavigationItem[] = [
  { name: "旧版概览", href: "/dashboard" },
  { name: "凭证设置", href: "/settings/credentials" },
  { name: "提供方状态", href: "/settings/providers" },
  { name: "成员与工作区", href: "/settings/members" },
];

/** 路径是否命中导航项。子路径也算命中。 */
export function isActiveRoute(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * 取当前路径命中的最具体导航项。
 *
 * 返回最长匹配。这样 /tools/tiktok 只高亮它自己，不同时高亮 /tools。
 * 没有命中时返回 null。
 */
export function activeNavigationHref(
  pathname: string,
  hrefs: readonly string[],
): string | null {
  let best: string | null = null;
  for (const href of hrefs) {
    if (!isActiveRoute(pathname, href)) continue;
    if (best === null || href.length > best.length) best = href;
  }
  return best;
}

/**
 * 能力详情页的路径。
 *
 * 工具标识可能含斜杠，必须先编码再拼进路径。
 */
export function toolDetailHref(toolId: string): string {
  return `/capabilities/${encodeURIComponent(toolId)}`;
}

/**
 * 打开能力详情。
 *
 * 单独抽出，测试可以用 router.push 的替身断言目标路径。
 */
export function openToolDetail(
  router: { push: (href: string) => void },
  toolId: string,
): void {
  router.push(toolDetailHref(toolId));
}

/** 能力详情页的四种状态。 */
export type ToolDetailState = "loading" | "not-found" | "error" | "ready";

/** 从错误对象读 HTTP 状态码。没有时返回 null。 */
function errorStatus(error: unknown): number | null {
  if (typeof error !== "object" || error === null) return null;
  if (!("status" in error)) return null;
  const value = (error as { status?: unknown }).status;
  return typeof value === "number" ? value : null;
}

/**
 * 判定能力详情页的状态。
 *
 * 404 归为「工具不存在」。其他错误归为「加载失败」。
 * 没有数据也没有错误时也按不存在处理，避免空白页。
 */
export function resolveToolDetailState(input: {
  isLoading: boolean;
  error: unknown;
  hasTool: boolean;
}): ToolDetailState {
  if (input.isLoading) return "loading";
  if (input.error) {
    return errorStatus(input.error) === 404 ? "not-found" : "error";
  }
  return input.hasTool ? "ready" : "not-found";
}
