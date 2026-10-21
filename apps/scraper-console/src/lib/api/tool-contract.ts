/**
 * 工具目录的纯契约。
 *
 * 本模块不导入任何运行时依赖。Node 测试可以直接加载它。
 * `tools.ts` 重导出这里的类型与常量，并补上请求函数。
 */

/**
 * 已知的参数值类型。
 * 后端字段是 `str | None`，目录演进后可能出现新值。
 * 消费方必须对未知值退化为文本框。
 */
export type ToolParamValueType =
  | "string"
  | "number"
  | "integer"
  | "enum"
  | "list"
  | "string_list"
  | "boolean";

/** 风险类别。与后端 `ToolRiskClass` 一致。 */
export type ToolRiskClass = "read" | "generate" | "outbound" | "compute";

/** 运行模式。与后端 `ToolRunMode` 一致。 */
export type ToolRunMode = "sync" | "async";

/** 输出类型。与后端 `ToolOutputKind` 一致。 */
export type ToolOutputKind =
  | "records"
  | "text"
  | "image"
  | "audio"
  | "video"
  | "file"
  | "action";

/** 可用性状态。与后端 `ToolAvailability` 一致。 */
export type ToolAvailabilityStatus =
  | "verified"
  | "config-gated"
  | "degraded"
  | "empty"
  | "untested"
  | "disabled";

/** 成本来源。与后端 `ToolCostHint.source` 一致。 */
export type ToolCostSource =
  | "upstream_estimate"
  | "platform_price"
  | "unknown";

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
  value_type: string | null;
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
  availability: ToolAvailabilityStatus;
  catalog_status: string;
  last_test_status: string | null;
  last_test_at: string | null;
  last_records_count: number | null;
  missing_configuration: string[];
};

/**
 * 成本声明。
 * `source` 区分成本来源。上游估算不是平台售价，两者不得混用。
 */
export type PublicToolCostHint = {
  summary: string | null;
  source: ToolCostSource;
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
  risk_class: ToolRiskClass;
  output_kind: ToolOutputKind;
  run_mode: ToolRunMode;
  cancellable: boolean;
  parameters: PublicToolParameter[];
  required_parameters: string[];
  optional_parameters: string[];
  cost: PublicToolCostHint;
  availability: PublicToolAvailability;
  execution_kind: string;
  executable_now: boolean;
  permanently_blocked: boolean;
  is_alias_view: boolean;
  canonical_tool_id: string;
  executable: boolean;
};

/** 目录里的一个分类聚合。与后端 `ToolCategory` 一致。 */
export type PublicToolCategory = {
  category: string;
  tool_count: number;
  executable_count: number;
};

/** 完整目录。与后端 `PublicToolCatalog` 一致。 */
export type PublicToolCatalog = {
  schema_version: string;
  contract_version: string;
  catalog_digest: string;
  tool_count: number;
  canonical_tool_count: number;
  executable_count: number;
  categories: PublicToolCategory[];
  tools: PublicTool[];
};

/**
 * 字段名清单。测试用它断言前端类型没有漂移。
 * 每个清单与 `tool_catalog/public.py` 的模型逐字段对应。
 */
export const PUBLIC_TOOL_PARAMETER_FIELDS = [
  "name",
  "required",
  "typed",
  "value_type",
  "description",
  "default",
  "allowed_values",
  "minimum",
  "maximum",
  "max_length",
  "type_enforced",
] as const;

export const PUBLIC_TOOL_AVAILABILITY_FIELDS = [
  "availability",
  "catalog_status",
  "last_test_status",
  "last_test_at",
  "last_records_count",
  "missing_configuration",
] as const;

export const PUBLIC_TOOL_COST_FIELDS = ["summary", "source"] as const;

export const PUBLIC_TOOL_FIELDS = [
  "tool_id",
  "contract_version",
  "label",
  "description",
  "category",
  "platform",
  "provider",
  "provider_group",
  "content_type",
  "risk_class",
  "output_kind",
  "run_mode",
  "cancellable",
  "parameters",
  "required_parameters",
  "optional_parameters",
  "cost",
  "availability",
  "execution_kind",
  "executable_now",
  "permanently_blocked",
  "is_alias_view",
  "canonical_tool_id",
  "executable",
] as const;

export const PUBLIC_TOOL_CATEGORY_FIELDS = [
  "category",
  "tool_count",
  "executable_count",
] as const;

export const PUBLIC_TOOL_CATALOG_FIELDS = [
  "schema_version",
  "contract_version",
  "catalog_digest",
  "tool_count",
  "canonical_tool_count",
  "executable_count",
  "categories",
  "tools",
] as const;

/**
 * 编译期字段检查。
 * 清单少一个字段或多一个字段，tsc 都会报错。
 */
type ExactFieldNames<T, K extends readonly string[]> =
  Exclude<keyof T, K[number]> extends never
    ? Exclude<K[number], keyof T> extends never
      ? true
      : never
    : never;

/* eslint-disable @typescript-eslint/no-unused-vars -- 这些常量只用于编译期字段检查。 */
const _parameterFieldsExact: ExactFieldNames<
  PublicToolParameter,
  typeof PUBLIC_TOOL_PARAMETER_FIELDS
> = true;
const _availabilityFieldsExact: ExactFieldNames<
  PublicToolAvailability,
  typeof PUBLIC_TOOL_AVAILABILITY_FIELDS
> = true;
const _costFieldsExact: ExactFieldNames<
  PublicToolCostHint,
  typeof PUBLIC_TOOL_COST_FIELDS
> = true;
const _toolFieldsExact: ExactFieldNames<
  PublicTool,
  typeof PUBLIC_TOOL_FIELDS
> = true;
const _categoryFieldsExact: ExactFieldNames<
  PublicToolCategory,
  typeof PUBLIC_TOOL_CATEGORY_FIELDS
> = true;
const _catalogFieldsExact: ExactFieldNames<
  PublicToolCatalog,
  typeof PUBLIC_TOOL_CATALOG_FIELDS
> = true;
/* eslint-enable @typescript-eslint/no-unused-vars */

/** 目录筛选条件。字段名与 `GET /api/tools` 的查询参数一一对应。 */
export type ToolFilters = Readonly<{
  query?: string | null;
  riskClass?: ToolRiskClass | null;
  executableNow?: boolean | null;
}>;

/**
 * 构造 `GET /api/tools` 的路径。
 * 空筛选不写入查询串。空白关键词也丢弃。
 * `executable_now=false` 是有效筛选，必须保留。
 */
export function buildToolsPath(filters: ToolFilters = {}): string {
  const params = new URLSearchParams();
  const query = filters.query?.trim();
  if (query) params.set("query", query);
  if (filters.riskClass) params.set("risk_class", filters.riskClass);
  if (filters.executableNow !== null && filters.executableNow !== undefined) {
    params.set("executable_now", filters.executableNow ? "true" : "false");
  }
  const search = params.toString();
  return search ? `/api/tools?${search}` : "/api/tools";
}
