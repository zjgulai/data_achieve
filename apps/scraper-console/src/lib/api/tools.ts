/**
 * 工具目录的请求层。
 *
 * 类型、字段清单与路径构造在 `tool-contract.ts`。
 * 本模块重导出它们，并补上两个请求函数。
 */

import { apiFetch } from "./client";
import {
  buildToolsPath,
  type PublicTool,
  type PublicToolCatalog,
  type ToolFilters,
} from "./tool-contract";

export * from "./tool-contract";

/** 读取目录。返回完整的 `PublicToolCatalog`。 */
export async function fetchTools(
  filters: ToolFilters = {},
): Promise<PublicToolCatalog> {
  return apiFetch<PublicToolCatalog>(buildToolsPath(filters));
}

/** 读取单个工具。未命中时服务端返回 404。 */
export async function fetchTool(toolId: string): Promise<PublicTool> {
  return apiFetch<PublicTool>(`/api/tools/${encodeURIComponent(toolId)}`);
}
