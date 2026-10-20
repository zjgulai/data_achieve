/**
 * 新旧路由对照表的只读副本。
 *
 * 来源：docs/architecture/【技术方案】DIH整站能力整合方案.md §4.3。
 * 该表在 P0 冻结。改动需产品确认。
 *
 * 本模块只描述重定向。保持路径的条目不在其中。
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

/** 保持路径的条目。仅记录，不产生重定向。 */
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

/** 本批次新增的路由。 */
export const NEW_ROUTES: readonly string[] = [
  "/connect",
  "/tools/[toolId]",
  "/settings/providers",
  "/settings/members",
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
