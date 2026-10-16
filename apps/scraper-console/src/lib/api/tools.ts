import { apiFetch } from "./client";

/**
 * 参数值类型。
 * 目录现值 6 种。另有两种情况要处理：
 * - `null`：参数无类型登记（`typed=false`）。
 * - 未知值：目录演进后可能出现。渲染器必须退化为文本框。
 */
export type ToolParamValueType =
  | "string"
  | "number"
  | "integer"
  | "enum"
  | "list"
  | "string_list"
  | "boolean";

/**
 * 单个参数的契约。
 * `typed=false` 时，除 `name` 与 `required` 外全为空值。
 * `type_enforced=false` 表示服务端实现不校验该参数类型。
 * 前端不得据此假定非法输入会被拒。
 */
export type PublicToolParameter = {
  name: string;
  required: boolean;
  typed: boolean;
  value_type: ToolParamValueType | null;
  description: string | null;
  default: unknown;
  allowed_values: string[];
  minimum: number | null;
  maximum: number | null;
  max_length: number | null;
  type_enforced: boolean;
};

/** 可用性视图。不含阻断原因原文。 */
export type PublicToolAvailability = {
  availability: string;
  catalog_status: string;
  last_test_status: string | null;
  last_test_at: string | null;
  last_records_count: number | null;
  missing_configuration: string[];
};

/**
 * 工具的对外描述。
 * `executable_now` 含环境因素。切到受限联网会变真。
 * `permanently_blocked` 是策略层的无条件拒绝。切换环境也不放行。
 */
export type PublicTool = {
  tool_id: string;
  contract_version: string;
  label: string;
  description: string;
  category: string;
  platform: string;
  provider: string;
  provider_group: string;
  content_type: string;
  risk_class: string;
  output_kind: string;
  run_mode: string;
  cancellable: boolean;
  parameters: PublicToolParameter[];
  required_parameters: string[];
  optional_parameters: string[];
  availability: PublicToolAvailability;
  execution_kind: string;
  executable_now: boolean;
  permanently_blocked: boolean;
  is_alias_view: boolean;
  canonical_tool_id: string;
  executable: boolean;
};

export async function fetchTool(toolId: string): Promise<PublicTool> {
  return apiFetch<PublicTool>(`/api/tools/${encodeURIComponent(toolId)}`);
}
