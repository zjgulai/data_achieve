import { apiFetch } from "./client";

/**
 * 单个 MCP 工具的策略行。字段与后端 McpToolPolicyItem
 * （apps/api/src/data_intelligence_hub/schemas/mcp_tool_policy.py）
 * 一一对应；事实源是 mcp_runtime/tool_registry.py 的策略注册表。
 */
export type McpToolPolicyItem = Readonly<{
  name: string;
  access_mode: "read" | "execute" | "control";
  requires_project: boolean;
  project_scope: string;
  consumes_quota: "none" | "per_call" | "per_row_worker" | "per_scheduled_run";
  run_mode: string;
  cancellable: boolean;
  preset_groups: string[];
}>;

/** GET /api/settings/mcp-tool-policies 的响应。 */
export type McpToolPolicies = Readonly<{
  registry_version: string;
  tool_count: number;
  tools: McpToolPolicyItem[];
  presets: Record<string, string[]>;
}>;

/** 读取 MCP 工具策略注册表。后端严格鉴权：未登录时 401。 */
export function fetchMcpToolPolicies(): Promise<McpToolPolicies> {
  return apiFetch<McpToolPolicies>("/api/settings/mcp-tool-policies");
}
