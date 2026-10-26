import assert from "node:assert/strict";
import test from "node:test";
import {
  PUBLIC_TOOL_AVAILABILITY_FIELDS,
  PUBLIC_TOOL_CATALOG_FIELDS,
  PUBLIC_TOOL_CATEGORY_FIELDS,
  PUBLIC_TOOL_COST_FIELDS,
  PUBLIC_TOOL_FIELDS,
  PUBLIC_TOOL_PARAMETER_FIELDS,
  buildToolsPath,
  type PublicTool,
} from "./tool-contract.ts";

/** 一个字段齐全的工具。tsc 会检查它与 `PublicTool` 一致。 */
function sampleTool(): PublicTool {
  return {
    tool_id: "anysearch_brand_media",
    contract_version: "tool.v1",
    label: "品牌媒体",
    description: "采集品牌相关的媒体内容。",
    category: "anysearch",
    platform: "anysearch",
    provider: "anysearch",
    provider_group: "search",
    content_type: "web",
    risk_class: "read",
    output_kind: "records",
    run_mode: "sync",
    cancellable: false,
    parameters: [
      {
        name: "query",
        required: true,
        typed: true,
        value_type: "string",
        description: "关键词",
        default: null,
        allowed_values: [],
        minimum: null,
        maximum: null,
        max_length: 100,
        type_enforced: true,
      },
    ],
    required_parameters: ["query"],
    optional_parameters: [],
    cost: { summary: "按次计费", source: "upstream_estimate" },
    availability: {
      availability: "verified",
      catalog_status: "verified",
      last_test_status: "success",
      last_test_at: "2026-10-20T00:00:00Z",
      last_records_count: 12,
      missing_configuration: [],
    },
    execution_kind: "provider_api",
    executable_now: true,
    permanently_blocked: false,
    is_alias_view: false,
    canonical_tool_id: "anysearch_brand_media",
    executable: true,
  };
}

function pathParams(path: string): URLSearchParams {
  return new URL(path, "http://console.test").searchParams;
}

test("PublicTool field names match the backend projection", () => {
  // 字段名写死。后端新增或删除字段时，这条断言与 tsc 检查一起拦住漂移。
  assert.deepEqual([...PUBLIC_TOOL_FIELDS].sort(), [
    "availability",
    "cancellable",
    "canonical_tool_id",
    "category",
    "content_type",
    "contract_version",
    "cost",
    "description",
    "executable",
    "executable_now",
    "execution_kind",
    "is_alias_view",
    "label",
    "optional_parameters",
    "output_kind",
    "parameters",
    "permanently_blocked",
    "platform",
    "provider",
    "provider_group",
    "required_parameters",
    "risk_class",
    "run_mode",
    "tool_id",
  ]);
});

test("nested PublicTool field names match the backend projection", () => {
  assert.deepEqual([...PUBLIC_TOOL_PARAMETER_FIELDS].sort(), [
    "allowed_values",
    "default",
    "description",
    "max_length",
    "maximum",
    "minimum",
    "name",
    "required",
    "type_enforced",
    "typed",
    "value_type",
  ]);
  assert.deepEqual([...PUBLIC_TOOL_AVAILABILITY_FIELDS].sort(), [
    "availability",
    "catalog_status",
    "last_records_count",
    "last_test_at",
    "last_test_status",
    "missing_configuration",
  ]);
  assert.deepEqual([...PUBLIC_TOOL_COST_FIELDS].sort(), ["source", "summary"]);
});

test("catalog field names match the backend projection", () => {
  assert.deepEqual([...PUBLIC_TOOL_CATEGORY_FIELDS].sort(), [
    "category",
    "executable_count",
    "tool_count",
  ]);
  assert.deepEqual([...PUBLIC_TOOL_CATALOG_FIELDS].sort(), [
    "canonical_tool_count",
    "catalog_digest",
    "categories",
    "contract_version",
    "executable_count",
    "schema_version",
    "tool_count",
    "tools",
  ]);
});

test("a full sample carries exactly the declared PublicTool fields", () => {
  const sample = sampleTool();
  assert.deepEqual(Object.keys(sample).sort(), [...PUBLIC_TOOL_FIELDS].sort());
});

test("buildToolsPath returns the bare path without filters", () => {
  assert.equal(buildToolsPath(), "/api/tools");
  assert.equal(
    buildToolsPath({ query: "", riskClass: null, executableNow: null }),
    "/api/tools",
  );
  assert.equal(buildToolsPath({ query: "   " }), "/api/tools");
});

test("buildToolsPath carries all three filters", () => {
  const path = buildToolsPath({
    query: "德国 吸乳器",
    riskClass: "outbound",
    executableNow: true,
  });
  assert.equal(path.startsWith("/api/tools?"), true);
  const params = pathParams(path);
  assert.equal(params.get("query"), "德国 吸乳器");
  assert.equal(params.get("risk_class"), "outbound");
  assert.equal(params.get("executable_now"), "true");
});

test("buildToolsPath keeps executable_now=false", () => {
  // false 是有效筛选。按真值判断会漏掉它。
  const params = pathParams(buildToolsPath({ executableNow: false }));
  assert.equal(params.get("executable_now"), "false");
});

test("buildToolsPath trims the keyword", () => {
  const params = pathParams(buildToolsPath({ query: "  tiktok  " }));
  assert.equal(params.get("query"), "tiktok");
});

test("buildToolsPath drops null and undefined filters", () => {
  const params = pathParams(
    buildToolsPath({ query: undefined, riskClass: undefined }),
  );
  assert.equal([...params.keys()].length, 0);
});

test("buildToolsPath encodes reserved characters", () => {
  const path = buildToolsPath({ query: "a&b=c" });
  assert.equal(pathParams(path).get("query"), "a&b=c");
  assert.equal(path.includes("a%26b%3Dc"), true);
});
