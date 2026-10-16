/**
 * URL 查询参数的读写工具。
 *
 * 页面的筛选状态写入 URL，以便分享与返回。
 * 本模块只处理字符串拼接，不依赖 React。
 */

/** 参数更新。值为 null 或空串时删除该键。 */
export type ParamUpdates = Record<string, string | null>;

/**
 * 在当前参数上应用更新，返回新的查询串。
 *
 * 不修改入参。空串与 null 都表示删除。
 */
export function mergeParams(current: URLSearchParams, updates: ParamUpdates): string {
  const next = new URLSearchParams(current);
  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
  }
  next.sort();
  return next.toString();
}

/** 把路径与查询串拼成 href。查询串为空时只返回路径。 */
export function hrefWithParams(pathname: string, query: string): string {
  return query ? `${pathname}?${query}` : pathname;
}

/** 度抖动的搜索词写入延时。毫秒。 */
export const SEARCH_DEBOUNCE_MS = 300;
