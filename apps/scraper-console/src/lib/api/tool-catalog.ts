import { apiFetch } from "./client";

/**
 * 工具目录摘要。
 *
 * 只含计数与摘要，不含 281 条条目。
 * 与 GET /api/tools 读同一事实源，摘要用于核对三处读到的是不是同一份目录。
 */
export type ToolCatalogSummary = {
  schema_version: string;
  contract_version: string;
  catalog_digest: string;
  tool_count: number;
  canonical_tool_count: number;
  executable_count: number;
  categories: Array<{
    category: string;
    tool_count: number;
    executable_count: number;
  }>;
};

export async function fetchToolCatalogSummary(): Promise<ToolCatalogSummary> {
  return apiFetch<ToolCatalogSummary>("/api/tool-catalog");
}
