/**
 * 快速采集表单的纯函数层。
 *
 * 字段来源是工具契约（`GET /api/tools` 的 `parameters`）。
 * 本模块不依赖 React。可单测。
 */

import type { PublicTool, PublicToolParameter } from "./api/tools";
import type { QuickCollectParamValue } from "./api/quick-collect";

/** 表单值。文本、数字、列表都用字符串。布尔用 true / false。 */
export type FormValue = string | boolean;

/** 表单值集合。键是参数名。 */
export type FormValues = Record<string, FormValue>;

/** 字段的控件类型。 */
export type FieldKind = "text" | "number" | "boolean" | "enum" | "list";

/** 下拉选项。 */
export type SelectOption = { value: string; label: string };

/** 一个表单字段。由契约参数派生。 */
export type ParamField = {
  name: string;
  label: string;
  kind: FieldKind;
  required: boolean;
  /** 契约登记了类型。false 表示只知道参数名。 */
  typed: boolean;
  /** 服务端强制校验类型。false 时前端不做类型拦截。 */
  typeEnforced: boolean;
  /** 整数类型。数字框据此限制步进。 */
  integer: boolean;
  placeholder: string;
  options: SelectOption[];
  minimum: number | null;
  maximum: number | null;
  /** list 的元素数上限。 */
  maxItems: number | null;
  description: string | null;
  defaultValue: FormValue;
};

/** 表单结构。fields 渲染成控件。presets 随提交静默发送。 */
export type ParamForm = {
  fields: ParamField[];
  presets: Record<string, QuickCollectParamValue>;
  /**
   * 服务端固定的目标地址。
   *
   * 来源是 `param_fields.url`。它随 presets 静默发送，
   * 用户在表单里改同一个键不会生效。
   * 界面必须把它渲染成只读，否则用户会以为可以改。
   */
  fixedTargetUrl: string | null;
};

/** 服务端保留键。不渲染，不发送。 */
const SERVER_RESERVED_KEYS = new Set([
  "execution_origin",
  "schedule_policy",
  "schedule_cron",
  "freshness_target_hours",
  "max_retry_attempts",
  "retry_delay_minutes",
  "retry_attempts_used",
]);

/** 高频参数名的中文标签。缺项时直接用参数名。 */
const PARAM_LABELS: Record<string, string> = {
  query: "查询词",
  keyword: "关键词",
  keywords: "关键词",
  search_query: "搜索词",
  searchTerms: "搜索词",
  search_terms: "搜索词",
  username: "用户名",
  unique_id: "账号名",
  user_id: "用户 ID",
  url: "网址",
  urls: "网址列表",
  startUrl: "起始网址",
  startUrls: "起始网址列表",
  profileUrls: "主页网址列表",
  productUrls: "商品网址列表",
  product_url: "商品网址",
  categoryUrls: "类目网址列表",
  queries: "查询词列表",
  max_items: "最大条数",
  maxItems: "最大条数",
  max_items_per_url: "每网址最大条数",
  maxQueries: "最大查询数",
  max_results: "最大结果数",
  num_results: "结果条数",
  limit: "条数上限",
  page: "页码",
  offset: "偏移量",
  depth: "深度",
  level: "层级",
  sites: "站点列表",
  modules: "模块列表",
  fields: "字段列表",
  tag: "标签",
  params: "附加参数",
  site: "限定站点",
  text: "返回正文",
  category: "类目",
  contents_mode: "内容模式",
  max_age_hours: "缓存时长",
  subpages: "子页数",
  include_domains: "包含域名",
  exclude_domains: "排除域名",
  exclude_source_domain: "排除来源域名",
  output_schema: "输出结构",
  summary_query: "摘要问题",
  system_prompt: "系统提示词",
  additional_queries: "追加查询词",
  start_published_date: "发布起始日",
  end_published_date: "发布截止日",
  text_max_characters: "正文长度上限",
  subpage_target: "子页目标",
  include_paths: "包含路径",
  exclude_paths: "排除路径",
  includeSpecSheet: "含规格表",
  includeCertificates: "含证书",
  includePackagingAndWeight: "含包装与重量",
  wanted_list: "目标字段列表",
  rules_path: "规则文件路径",
  save_rules: "保存规则",
  country: "国家",
  language: "语言",
  region: "地区",
};

/** 取参数的中文标签。 */
export function paramLabel(name: string): string {
  return PARAM_LABELS[name] ?? name;
}

/** 提示的解析结果。 */
export type HintInfo = {
  /** 原始提示文本。 */
  raw: string;
  /** 示例文本。用于 placeholder。 */
  placeholder: string | null;
  /** 下拉选项。管道枚举或数字头管道产生。 */
  options: SelectOption[];
  /** 单值预设。可作预填值。 */
  preset: QuickCollectParamValue;
  /** 布尔字面量。true / false 产生。 */
  boolean: boolean | null;
};

const EMPTY_HINT: HintInfo = {
  raw: "",
  placeholder: null,
  options: [],
  preset: null,
  boolean: null,
};

/** 解析 placeholder 形态的提示。形如 `string (e.g. xxx)`。 */
function parsePlaceholderHint(text: string): string | null {
  const m = /^(?:string|object|array|list)\s*\(e\.g\.\s*(.+?)\)$/i.exec(text.trim());
  return m ? m[1] : null;
}

/** 把管道段转成选项。数字头保留数字为值。 */
function parsePipeOptions(text: string): SelectOption[] {
  const parts = text.split("|").map((s) => s.trim()).filter(Boolean);
  if (parts.length < 2) return [];
  return parts.map((seg) => {
    const m = /^(-?\d+)\b/.exec(seg);
    return m ? { value: m[1], label: seg } : { value: seg, label: seg };
  });
}

/** 把 JSON 解析结果收窄为可提交的参数值。不可收窄时返回 null。 */
export function toParamValue(value: unknown): QuickCollectParamValue | null {
  if (value === null) return null;
  const kind = typeof value;
  if (kind === "string" || kind === "number" || kind === "boolean") {
    return value as string | number | boolean;
  }
  if (Array.isArray(value)) {
    if (value.every((v) => typeof v === "string")) return value as string[];
    if (value.every((v) => typeof v === "number")) return value as number[];
    return null;
  }
  if (kind === "object") return value as Record<string, unknown>;
  return null;
}

/** 把提示值转成预设的 JSON 值。 */
export function parsePresetValue(text: string): QuickCollectParamValue | null {
  const t = text.trim();
  if (t === "true") return true;
  if (t === "false") return false;
  if (/^-?\d+$/.test(t)) return Number(t);
  if ((t.startsWith("[") && t.endsWith("]")) || (t.startsWith("{") && t.endsWith("}"))) {
    try {
      return toParamValue(JSON.parse(t));
    } catch {
      return text;
    }
  }
  return text;
}

/** 解析一条 `param_fields` 提示。 */
export function classifyHint(hint: string | null | undefined): HintInfo {
  if (hint === null || hint === undefined) return EMPTY_HINT;
  const raw = String(hint).trim();
  if (!raw) return EMPTY_HINT;

  const placeholder = parsePlaceholderHint(raw);
  if (placeholder !== null) {
    return { ...EMPTY_HINT, raw, placeholder };
  }

  const options = parsePipeOptions(raw);
  if (options.length > 0) {
    return { ...EMPTY_HINT, raw, options };
  }

  if (raw === "true" || raw === "false") {
    const b = raw === "true";
    return { ...EMPTY_HINT, raw, boolean: b, preset: b };
  }

  return { ...EMPTY_HINT, raw, preset: parsePresetValue(raw) };
}

/** 契约的取值类型。未知类型返回 null。 */
function knownValueType(p: PublicToolParameter): string | null {
  if (!p.typed) return null;
  const vt = p.value_type;
  if (vt === null || vt === undefined) return null;
  return vt;
}

/** 判定字段的控件类型。 */
export function kindOf(param: PublicToolParameter, hint: HintInfo): FieldKind {
  const vt = knownValueType(param);
  if (vt === "integer" || vt === "number") return "number";
  if (vt === "boolean") return "boolean";
  if (vt === "list" || vt === "string_list") return "list";
  if (vt === "enum") return param.allowed_values.length > 0 ? "enum" : "text";

  // 无类型参数靠提示补类型。
  if (hint.boolean !== null) return "boolean";
  if (hint.options.length > 0) return "enum";
  return "text";
}

/** 构造下拉选项。 */
function buildOptions(param: PublicToolParameter, hint: HintInfo): SelectOption[] {
  const vt = knownValueType(param);
  if (vt === "enum" && param.allowed_values.length > 0) {
    const opts: SelectOption[] = param.allowed_values.map((v) => ({
      value: v,
      // 空串选项是合法值。给一个可读标签。
      label: v === "" ? "（默认）" : v,
    }));
    if (param.default === "" && !param.allowed_values.includes("")) {
      opts.unshift({ value: "", label: "（默认）" });
    }
    return opts;
  }
  return hint.options;
}

/** 把契约默认值转成表单值。 */
function toFormValue(value: unknown, kind: FieldKind): FormValue {
  if (kind === "boolean") return value === true;
  if (kind === "list") {
    if (Array.isArray(value)) return value.map((v) => String(v)).join("\n");
    return value === null || value === undefined ? "" : String(value);
  }
  if (value === null || value === undefined) return "";
  return String(value);
}

/** 取字段的初始值。契约默认值优先。 */
function initialValue(param: PublicToolParameter, kind: FieldKind, hint: HintInfo): FormValue {
  if (param.default !== null && param.default !== undefined) {
    return toFormValue(param.default, kind);
  }
  if (knownValueType(param) !== null) return kind === "boolean" ? false : "";
  // 无类型参数用提示补齐初始值。
  if (kind === "boolean") return hint.boolean === true;
  if (kind === "enum" && hint.options.length > 0) return hint.options[0].value;
  if (hint.preset !== null && typeof hint.preset !== "object") {
    return kind === "list" ? String(hint.preset) : String(hint.preset);
  }
  return "";
}

/** 提示里的键不在契约时，作为固定预设。 */
function collectPresets(
  parameters: PublicToolParameter[],
  paramFields: Record<string, string> | null | undefined
): Record<string, QuickCollectParamValue> {
  const presets: Record<string, QuickCollectParamValue> = {};
  if (!paramFields) return presets;
  const names = new Set(parameters.map((p) => p.name));
  for (const [key, hint] of Object.entries(paramFields)) {
    if (names.has(key) || SERVER_RESERVED_KEYS.has(key)) continue;
    const info = classifyHint(hint);
    if (info.preset !== null) presets[key] = info.preset;
  }
  return presets;
}

/**
 * 由契约构造表单。
 *
 * `tool` 为空时返回空表单。调用方据此渲染错误态。
 */
export function buildForm(
  tool: PublicTool | null | undefined,
  paramFields: Record<string, string> | null | undefined
): ParamForm {
  if (!tool || !Array.isArray(tool.parameters)) {
    return { fields: [], presets: {}, fixedTargetUrl: null };
  }

  const fields: ParamField[] = [];
  for (const param of tool.parameters) {
    if (SERVER_RESERVED_KEYS.has(param.name)) continue;
    const hint = classifyHint(paramFields?.[param.name]);
    const kind = kindOf(param, hint);
    const vt = knownValueType(param);
    fields.push({
      name: param.name,
      label: paramLabel(param.name),
      kind,
      required: param.required,
      typed: param.typed,
      typeEnforced: param.type_enforced,
      integer: vt === "integer",
      placeholder: hint.placeholder ?? (hint.options.length > 0 && vt === null ? "请选择" : ""),
      options: buildOptions(param, hint),
      minimum: param.minimum === null ? null : Math.trunc(param.minimum),
      maximum: param.maximum === null ? null : Math.trunc(param.maximum),
      maxItems: param.value_type === "string_list" || param.value_type === "list" ? param.max_length : null,
      description: param.description,
      defaultValue: initialValue(param, kind, hint),
    });
  }

  const fixedRaw = paramFields?.url;
  const fixedTargetUrl =
    typeof fixedRaw === "string" && fixedRaw.trim() !== "" ? fixedRaw.trim() : null;

  return {
    fields,
    presets: collectPresets(tool.parameters, paramFields),
    fixedTargetUrl,
  };
}

/** 取表单的初始值集合。 */
export function buildInitialValues(form: ParamForm): FormValues {
  const out: FormValues = {};
  for (const f of form.fields) out[f.name] = f.defaultValue;
  return out;
}

/** 列表字段的分行文本转数组。去空行。 */
export function splitList(raw: string): string[] {
  return raw
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/** 判定单个字段是否为空。 */
export function isEmptyValue(field: ParamField, value: FormValue | undefined): boolean {
  if (field.kind === "boolean") return false;
  if (field.kind === "list") {
    const raw = typeof value === "string" ? value : "";
    return splitList(raw).length === 0;
  }
  const raw = typeof value === "string" ? value.trim() : "";
  if (raw.length > 0) return false;
  // 枚举的空串是合法值。
  if (field.kind === "enum" && field.options.some((o) => o.value === "")) return false;
  return true;
}

/** 判定是否有必填项未填。 */
export function hasEmptyRequired(form: ParamForm, values: FormValues): boolean {
  return form.fields.some((f) => f.required && isEmptyValue(f, values[f.name]));
}

/**
 * 序列化提交参数。
 *
 * 规则：
 * - 只发送当前契约里的参数。白名单化。
 * - 文本空串省略。数字框清空省略。修复 `Number("") === 0`。
 * - 布尔始终发送。
 * - 列表始终发数组。
 * - 固定预设并入。
 */
export function serializeParams(
  form: ParamForm,
  values: FormValues
): Record<string, QuickCollectParamValue> {
  const out: Record<string, QuickCollectParamValue> = {};

  for (const f of form.fields) {
    if (SERVER_RESERVED_KEYS.has(f.name)) continue;
    const v = values[f.name];

    if (f.kind === "boolean") {
      out[f.name] = v === true;
      continue;
    }

    if (f.kind === "list") {
      const raw = typeof v === "string" ? v : "";
      out[f.name] = splitList(raw);
      continue;
    }

    const raw = typeof v === "string" ? v : v === undefined ? "" : String(v);

    if (f.kind === "number") {
      const trimmed = raw.trim();
      if (!trimmed) continue;
      const n = Number(trimmed);
      if (!Number.isFinite(n)) continue;
      out[f.name] = f.integer ? Math.trunc(n) : n;
      continue;
    }

    if (f.kind === "enum") {
      // 枚举的空串是合法值。照发。
      if (raw === "" && !f.options.some((o) => o.value === "")) continue;
      out[f.name] = raw;
      continue;
    }

    if (raw === "") continue;
    out[f.name] = raw;
  }

  for (const [key, value] of Object.entries(form.presets)) {
    if (SERVER_RESERVED_KEYS.has(key)) continue;
    if (key in out) continue;
    out[key] = value;
  }

  return out;
}

/** 提交被阻断的原因。null 表示可提交。 */
export type SubmitBlockReason =
  | "pending"
  | "no_project"
  | "policy"
  | "unavailable"
  | "missing_config"
  | "permanently_blocked"
  | "contract_unavailable"
  | "empty_required";

/** 提交门控的输入。 */
export type SubmitGateInput = {
  projectId: string;
  /** 端点是否可采集。已含状态与策略阻断判定。 */
  endpointAllowed: boolean;
  /** 端点状态。用于区分「未验证」与「策略拒绝」。 */
  endpointStatus?: string;
  /** 运行证据的可用性。缺配置时与策略拒绝是两回事。 */
  availability?: string;
  /** 缺失的配置项。非空表示可配置后恢复。 */
  missingConfiguration?: readonly string[];
  /** 工具契约是否永久阻断。契约未加载时为 false。 */
  permanentlyBlocked: boolean;
  /** 契约是否加载中。 */
  toolLoading: boolean;
  /** 契约是否加载失败。 */
  toolFailed: boolean;
  /** 端点的必填参数个数。来自目录。 */
  endpointRequiredCount: number;
  form: ParamForm;
  values: FormValues;
  isPending: boolean;
};

/** 求提交门控。 */
export function evaluateSubmit(input: SubmitGateInput): SubmitBlockReason | null {
  if (input.isPending) return "pending";
  if (!input.projectId) return "no_project";
  if (!input.endpointAllowed) {
    // 区分三种阻断：未验证、缺配置、策略拒绝。
    // 三者的处置不同，混成一个提示会让用户误判。
    if (input.missingConfiguration && input.missingConfiguration.length > 0) {
      return "missing_config";
    }
    if (input.availability === "disabled" || input.availability === "empty") {
      return "unavailable";
    }
    if (input.endpointStatus && input.endpointStatus !== "verified") {
      return "unavailable";
    }
    return "policy";
  }
  if (input.permanentlyBlocked) return "permanently_blocked";
  // 契约没加载好，但端点有必填参数。此时不得放行。
  if ((input.toolFailed || input.toolLoading) && input.endpointRequiredCount > 0) {
    return "contract_unavailable";
  }
  if (hasEmptyRequired(input.form, input.values)) return "empty_required";
  return null;
}

/** 提交门控的提示文案。 */
export function submitBlockMessage(reason: SubmitBlockReason | null): string | null {
  switch (reason) {
    case "pending":
      return null;
    case "no_project":
      return "请先选择项目。";
    case "policy":
      return "当前执行环境不放行该端点。";
    case "unavailable":
      return "该端点尚未验证或当前不可用。请稍后再试或换端点。";
    case "missing_config":
      return "该端点缺少必要配置。请联系管理员补齐凭据或域名授权。";
    case "permanently_blocked":
      return "该端点被策略永久阻断。换执行环境也不放行。";
    case "contract_unavailable":
      return "参数契约加载失败。请重试。";
    case "empty_required":
      return "请填写全部必填参数。";
    default:
      return null;
  }
}
