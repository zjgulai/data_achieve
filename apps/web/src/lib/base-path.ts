/**
 * 部署子路径支持。
 *
 * 生产上 apps/web 挂在 `scrapy.luteos.com/insight`，构建期注入
 * `NEXT_PUBLIC_BASE_PATH=/insight`。本地开发与现有 E2E 不设该变量，
 * 前缀为空字符串，行为与之前完全一致。
 *
 * 为什么需要这个工具：Next 的 `next/link`、`router.push`、服务端
 * `redirect` 都会自动加 basePath，但 `window.location.pathname` 读到的是
 * **含前缀**的真实路径，而 `buildIntelligenceListHref` 这类函数生成的是
 * **不含前缀**的路由。两者直接比较恒不相等，写回 URL 时会丢掉前缀。
 * 所以需要在边界上做一次显式换算。
 */

/** 构建期前缀。空字符串表示挂在站点根。 */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

/**
 * 去掉前缀，得到「路由视角」的路径。
 *
 * 用于把 `window.location.pathname` 转成与 next/link 生成值同一口径。
 * 不含前缀的路径原样返回。
 */
export function stripBasePath(pathname: string): string {
  if (!BASE_PATH) {
    return pathname;
  }
  if (pathname === BASE_PATH) {
    return "/";
  }
  if (pathname.startsWith(`${BASE_PATH}/`)) {
    return pathname.slice(BASE_PATH.length);
  }
  return pathname;
}

/**
 * 加上前缀，得到「浏览器视角」的路径。
 *
 * 用于需要写进 `history.replaceState` 或分享链接的场景。
 * 已经带前缀的路径不会重复添加。
 */
export function withBasePath(pathname: string): string {
  if (!BASE_PATH) {
    return pathname;
  }
  if (pathname === BASE_PATH || pathname.startsWith(`${BASE_PATH}/`)) {
    return pathname;
  }
  return pathname === "/" ? BASE_PATH || "/" : `${BASE_PATH}${pathname}`;
}
