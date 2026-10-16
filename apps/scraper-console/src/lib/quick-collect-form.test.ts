import assert from "node:assert/strict";
import test from "node:test";
import {
  buildForm,
  buildInitialValues,
  classifyHint,
  dedupeByEndpointType,
  evaluateSubmit,
  hasEmptyRequired,
  parsePresetValue,
  serializeParams,
  splitList,
  submitBlockMessage,
} from "./quick-collect-form.ts";
import type { PublicTool, PublicToolParameter } from "./api/tools.ts";

/** 造一个契约参数。默认无类型。 */
function param(over: Partial<PublicToolParameter> = {}): PublicToolParameter {
  return {
    name: "p",
    required: false,
    typed: false,
    value_type: null,
    description: null,
    default: null,
    allowed_values: [],
    minimum: null,
    maximum: null,
    max_length: null,
    type_enforced: true,
    ...over,
  };
}

/** 造一个工具。 */
function tool(params: PublicToolParameter[], over: Partial<PublicTool> = {}): PublicTool {
  return {
    tool_id: "t",
    contract_version: "tool.v1",
    label: "T",
    description: "",
    category: "c",
    platform: "p",
    provider: "pv",
    provider_group: "g",
    content_type: "web",
    risk_class: "read",
    output_kind: "records",
    run_mode: "sync",
    cancellable: false,
    parameters: params,
    required_parameters: params.filter((p) => p.required).map((p) => p.name),
    optional_parameters: params.filter((p) => !p.required).map((p) => p.name),
    availability: {
      availability: "config-gated",
      catalog_status: "verified",
      last_test_status: null,
      last_test_at: null,
      last_records_count: null,
      missing_configuration: [],
    },
    execution_kind: "provider_api",
    executable_now: false,
    permanently_blocked: false,
    is_alias_view: false,
    canonical_tool_id: "t",
    executable: false,
    ...over,
  };
}

/* ── 提示解析 ── */

test("placeholder hint keeps the example text", () => {
  const h = classifyHint("string (e.g. code.doc)");
  assert.equal(h.placeholder, "code.doc");
  assert.deepEqual(h.options, []);
});

test("object hint with JSON example becomes a placeholder", () => {
  const h = classifyHint('object (e.g. {"library": "golang"})');
  assert.equal(h.placeholder, '{"library": "golang"}');
});

test("pipe hint becomes enum options", () => {
  const h = classifyHint("highlights|text|summary|none");
  assert.deepEqual(
    h.options.map((o) => o.value),
    ["highlights", "text", "summary", "none"]
  );
});

test("numbered pipe hint keeps the number as the value", () => {
  const h = classifyHint("0 (实时) | -1 (仅缓存)");
  assert.deepEqual(h.options.map((o) => o.value), ["0", "-1"]);
});

test("boolean hint carries a boolean preset", () => {
  assert.equal(classifyHint("false").boolean, false);
  assert.equal(classifyHint("true").boolean, true);
});

test("parsePresetValue decodes literals", () => {
  assert.equal(parsePresetValue("true"), true);
  assert.equal(parsePresetValue("10"), 10);
  assert.deepEqual(parsePresetValue('["a","b"]'), ["a", "b"]);
  assert.equal(parsePresetValue("news"), "news");
});

/* ── 字段构造 ── */

test("untyped required parameter renders as a required text field", () => {
  const form = buildForm(tool([param({ name: "inputs", required: true })]), null);
  const f = form.fields[0];
  assert.equal(f.kind, "text");
  assert.equal(f.required, true);
  assert.equal(f.typed, false);
});

test("integer parameter keeps bounds and forces integers", () => {
  const form = buildForm(
    tool([param({ name: "depth", typed: true, value_type: "integer", minimum: 1, maximum: 3, default: 1 })]),
    null
  );
  const f = form.fields[0];
  assert.equal(f.kind, "number");
  assert.equal(f.integer, true);
  assert.equal(f.minimum, 1);
  assert.equal(f.maximum, 3);
  assert.equal(f.defaultValue, "1");
});

test("float bounds are truncated for integer fields", () => {
  // 契约里边界一律是浮点写法。
  const form = buildForm(
    tool([param({ name: "n", typed: true, value_type: "integer", minimum: 1.0, maximum: 50.0 })]),
    null
  );
  assert.equal(form.fields[0].minimum, 1);
  assert.equal(form.fields[0].maximum, 50);
});

test("enum parameter exposes allowed values and preselects the default", () => {
  const form = buildForm(
    tool([
      param({
        name: "contents_mode",
        typed: true,
        value_type: "enum",
        allowed_values: ["highlights", "text", "summary"],
        default: "text",
      }),
    ]),
    null
  );
  const f = form.fields[0];
  assert.equal(f.kind, "enum");
  assert.deepEqual(f.options.map((o) => o.value), ["highlights", "text", "summary"]);
  assert.equal(f.defaultValue, "text");
});

test("empty-string enum value stays selectable", () => {
  const form = buildForm(
    tool([
      param({
        name: "category",
        typed: true,
        value_type: "enum",
        allowed_values: ["", "news"],
        default: "",
      }),
    ]),
    null
  );
  const f = form.fields[0];
  assert.ok(f.options.some((o) => o.value === ""));
});

test("list parameter joins defaults by newline and reports the item cap", () => {
  const form = buildForm(
    tool([
      param({
        name: "urls",
        typed: true,
        value_type: "string_list",
        required: true,
        max_length: 100,
      }),
    ]),
    null
  );
  const f = form.fields[0];
  assert.equal(f.kind, "list");
  assert.equal(f.maxItems, 100);
});

test("string parameter does not invent a max length", () => {
  const form = buildForm(tool([param({ name: "q", typed: true, value_type: "string", required: true })]), null);
  assert.equal(form.fields[0].maxItems, null);
});

test("boolean parameter becomes a checkbox", () => {
  const form = buildForm(
    tool([param({ name: "flag", typed: true, value_type: "boolean", default: true })]),
    null
  );
  assert.equal(form.fields[0].kind, "boolean");
  assert.equal(form.fields[0].defaultValue, true);
});

test("unknown value type degrades to text", () => {
  const form = buildForm(
    tool([param({ name: "x", typed: true, value_type: "quantum" as never })]),
    null
  );
  assert.equal(form.fields[0].kind, "text");
});

test("server reserved keys are not rendered", () => {
  const form = buildForm(
    tool([
      param({ name: "query", typed: true, value_type: "string" }),
      param({ name: "schedule_cron" }),
      param({ name: "execution_origin" }),
    ]),
    null
  );
  assert.deepEqual(form.fields.map((f) => f.name), ["query"]);
});

test("hint keys absent from the contract become presets", () => {
  // exa 端点的 search_type 与 category 只存在于提示里。
  const form = buildForm(
    tool([param({ name: "query", typed: true, value_type: "string", required: true })]),
    { search_type: "deep", category: "news" }
  );
  assert.deepEqual(form.presets, { search_type: "deep", category: "news" });
  assert.deepEqual(form.fields.map((f) => f.name), ["query"]);
});

test("hint keys present in the contract are not presets", () => {
  const form = buildForm(
    tool([param({ name: "num_results", typed: true, value_type: "integer" })]),
    { num_results: "10" }
  );
  assert.deepEqual(form.presets, {});
});

test("a null tool yields an empty form", () => {
  assert.deepEqual(buildForm(null, null), { fields: [], presets: {} });
});

/* ── 值处理 ── */

test("splitList trims and drops blank lines", () => {
  assert.deepEqual(splitList("a\n\n  b  \n"), ["a", "b"]);
  assert.deepEqual(splitList("   "), []);
});

test("empty required text blocks submission", () => {
  const form = buildForm(tool([param({ name: "q", required: true, typed: true, value_type: "string" })]), null);
  assert.equal(hasEmptyRequired(form, buildInitialValues(form)), true);
  assert.equal(hasEmptyRequired(form, { q: "x" }), false);
});

test("a required list with no items blocks submission", () => {
  const form = buildForm(
    tool([param({ name: "urls", required: true, typed: true, value_type: "string_list" })]),
    null
  );
  assert.equal(hasEmptyRequired(form, { urls: "" }), true);
  assert.equal(hasEmptyRequired(form, { urls: "a.com" }), false);
});

test("booleans are never treated as empty", () => {
  const form = buildForm(
    tool([param({ name: "flag", required: true, typed: true, value_type: "boolean" })]),
    null
  );
  assert.equal(hasEmptyRequired(form, { flag: false }), false);
});

test("an empty-string enum option counts as filled", () => {
  const form = buildForm(
    tool([
      param({
        name: "category",
        required: true,
        typed: true,
        value_type: "enum",
        allowed_values: ["", "news"],
      }),
    ]),
    null
  );
  assert.equal(hasEmptyRequired(form, { category: "" }), false);
});

/* ── 序列化 ── */

test("empty text is omitted instead of sent as an empty string", () => {
  const form = buildForm(
    tool([param({ name: "q", required: true, typed: true, value_type: "string" })]),
    null
  );
  assert.deepEqual(serializeParams(form, { q: "" }), {});
});

test("a cleared number field is omitted instead of becoming 0", () => {
  // 修复点：Number("") === 0 会把空值变成 0。
  const form = buildForm(
    tool([param({ name: "n", typed: true, value_type: "integer" })]),
    null
  );
  assert.deepEqual(serializeParams(form, { n: "" }), {});
});

test("integer values are coerced to numbers", () => {
  const form = buildForm(
    tool([param({ name: "n", typed: true, value_type: "integer" })]),
    null
  );
  assert.deepEqual(serializeParams(form, { n: "20" }), { n: 20 });
});

test("list values are sent as arrays", () => {
  const form = buildForm(
    tool([param({ name: "urls", typed: true, value_type: "string_list", required: true })]),
    null
  );
  assert.deepEqual(serializeParams(form, { urls: "a.com\nb.com" }), { urls: ["a.com", "b.com"] });
  assert.deepEqual(serializeParams(form, { urls: "" }), { urls: [] });
});

test("booleans are sent as real booleans", () => {
  const form = buildForm(
    tool([param({ name: "flag", typed: true, value_type: "boolean" })]),
    null
  );
  assert.deepEqual(serializeParams(form, { flag: true }), { flag: true });
  assert.deepEqual(serializeParams(form, { flag: false }), { flag: false });
});

test("unknown fields are not forwarded", () => {
  // 上一个端点的残留值不得串台。
  const form = buildForm(
    tool([param({ name: "q", required: true, typed: true, value_type: "string" })]),
    null
  );
  assert.deepEqual(serializeParams(form, { q: "x", startUrls: "stale", maxItems: "99" }), { q: "x" });
});

test("presets are merged in and cannot be overwritten", () => {
  const form = buildForm(
    tool([param({ name: "query", required: true, typed: true, value_type: "string" })]),
    { search_type: "deep" }
  );
  assert.deepEqual(serializeParams(form, { query: "x", search_type: "fast" }), {
    query: "x",
    search_type: "deep",
  });
});

test("reserved keys are never sent", () => {
  const form = buildForm(
    tool([param({ name: "query", required: true, typed: true, value_type: "string" })]),
    null
  );
  assert.deepEqual(
    serializeParams(form, { query: "x", schedule_cron: "* * * * *", execution_origin: "manual" }),
    { query: "x" }
  );
});

/* ── 提交门控 ── */

function gate(over: Partial<Parameters<typeof evaluateSubmit>[0]> = {}) {
  const form = buildForm(
    tool([param({ name: "q", required: true, typed: true, value_type: "string" })]),
    null
  );
  return {
    projectId: "p1",
    endpointAllowed: true,
    permanentlyBlocked: false,
    toolLoading: false,
    toolFailed: false,
    endpointRequiredCount: 1,
    form,
    values: { q: "x" } as Record<string, unknown>,
    isPending: false,
    ...over,
  } as Parameters<typeof evaluateSubmit>[0];
}

test("a filled form is submittable", () => {
  assert.equal(evaluateSubmit(gate()), null);
});

test("a missing project blocks submission", () => {
  assert.equal(evaluateSubmit(gate({ projectId: "" })), "no_project");
});

test("an empty required field blocks submission", () => {
  assert.equal(evaluateSubmit(gate({ values: { q: "" } })), "empty_required");
});

test("a permanently blocked tool blocks submission", () => {
  assert.equal(evaluateSubmit(gate({ permanentlyBlocked: true })), "permanently_blocked");
});

test("a policy-blocked endpoint blocks submission", () => {
  assert.equal(evaluateSubmit(gate({ endpointAllowed: false })), "policy");
});

test("a failed contract blocks submission when the endpoint requires parameters", () => {
  assert.equal(evaluateSubmit(gate({ toolFailed: true })), "contract_unavailable");
});

test("a failed contract does not block an endpoint without required parameters", () => {
  const form = buildForm(tool([param({ name: "opt", typed: true, value_type: "string" })]), null);
  assert.equal(
    evaluateSubmit(gate({ toolFailed: true, endpointRequiredCount: 0, form, values: {} })),
    null
  );
});

test("an endpoint with no parameters stays submittable", () => {
  const form = buildForm(tool([]), null);
  assert.equal(
    evaluateSubmit(gate({ toolLoading: true, endpointRequiredCount: 0, form, values: {} })),
    null
  );
});

test("every block reason except pending has a message", () => {
  assert.equal(submitBlockMessage(null), null);
  assert.equal(submitBlockMessage("pending"), null);
  for (const reason of ["no_project", "policy", "permanently_blocked", "contract_unavailable", "empty_required"] as const) {
    assert.ok(submitBlockMessage(reason));
  }
});

/* ── 批量去重 ── */

test("dedupeByEndpointType keeps the first row of each type", () => {
  const rows = [
    { endpoint_type: "public_feed", label: "A" },
    { endpoint_type: "public_feed", label: "B" },
    { endpoint_type: "generic_web", label: "C" },
    { endpoint_type: "public_feed", label: "D" },
  ];
  assert.deepEqual(dedupeByEndpointType(rows), [
    { endpoint_type: "public_feed", label: "A" },
    { endpoint_type: "generic_web", label: "C" },
  ]);
});
