import assert from "node:assert/strict";
import test from "node:test";
import {
  RISK_CLASS_LABELS,
  RISK_CLASS_ORDER,
  costHintOf,
  executabilityOf,
  hasActiveFilters,
  listState,
  paginate,
  parseExecutableFilter,
  parsePage,
  parseRiskClass,
  riskClassLabel,
} from "./capabilities.ts";
import type { PublicTool } from "./api/tools.ts";

/** 造一个可覆盖的工具。默认是当前可执行。 */
function tool(over: Partial<PublicTool> = {}): PublicTool {
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
    parameters: [],
    required_parameters: [],
    optional_parameters: [],
    cost: { summary: null, source: "unknown" },
    availability: {
      availability: "verified",
      catalog_status: "verified",
      last_test_status: null,
      last_test_at: null,
      last_records_count: null,
      missing_configuration: [],
    },
    execution_kind: "provider_api",
    executable_now: true,
    permanently_blocked: false,
    is_alias_view: false,
    canonical_tool_id: "t",
    executable: true,
    ...over,
  };
}

function withAvailability(
  over: Partial<PublicTool>,
  availability: PublicTool["availability"],
): PublicTool {
  return tool({ ...over, availability });
}

/* ── 筛选参数 ── */

test("parseRiskClass accepts the four backend values", () => {
  for (const value of RISK_CLASS_ORDER) {
    assert.equal(parseRiskClass(value), value);
  }
});

test("parseRiskClass rejects unknown and empty values", () => {
  assert.equal(parseRiskClass("bogus"), null);
  assert.equal(parseRiskClass(""), null);
  assert.equal(parseRiskClass(null), null);
  assert.equal(parseRiskClass(undefined), null);
});

test("parseExecutableFilter distinguishes false from absent", () => {
  assert.equal(parseExecutableFilter("true"), true);
  assert.equal(parseExecutableFilter("false"), false);
  assert.equal(parseExecutableFilter("1"), null);
  assert.equal(parseExecutableFilter(""), null);
  assert.equal(parseExecutableFilter(null), null);
});

test("parsePage clamps invalid values to page one", () => {
  assert.equal(parsePage("1"), 1);
  assert.equal(parsePage("12"), 12);
  assert.equal(parsePage("0"), 1);
  assert.equal(parsePage("-3"), 1);
  assert.equal(parsePage("2.5"), 1);
  assert.equal(parsePage("abc"), 1);
  assert.equal(parsePage(""), 1);
  assert.equal(parsePage(null), 1);
});

test("risk labels cover every backend risk class", () => {
  for (const value of RISK_CLASS_ORDER) {
    assert.equal(typeof RISK_CLASS_LABELS[value], "string");
    assert.equal(RISK_CLASS_LABELS[value].length > 0, true);
  }
  // 未知值原样返回，界面不丢信息。
  assert.equal(riskClassLabel("future_class"), "future_class");
});

test("hasActiveFilters sees each filter", () => {
  assert.equal(
    hasActiveFilters({ query: "", riskClass: null, executableNow: null }),
    false,
  );
  assert.equal(
    hasActiveFilters({ query: " tiktok ", riskClass: null, executableNow: null }),
    true,
  );
  assert.equal(
    hasActiveFilters({ query: "", riskClass: "read", executableNow: null }),
    true,
  );
  assert.equal(
    hasActiveFilters({ query: "", riskClass: null, executableNow: false }),
    true,
  );
});

/* ── 分页边界 ── */

const items = Array.from({ length: 283 }, (_, index) => index + 1);

test("paginate returns the first page", () => {
  const page = paginate(items, 1, 20);
  assert.equal(page.items.length, 20);
  assert.equal(page.items[0], 1);
  assert.equal(page.items[19], 20);
  assert.equal(page.total, 283);
  assert.equal(page.totalPages, 15);
  assert.equal(page.start, 1);
  assert.equal(page.end, 20);
});

test("paginate returns a short last page", () => {
  const page = paginate(items, 15, 20);
  assert.equal(page.items.length, 3);
  assert.equal(page.items[0], 281);
  assert.equal(page.start, 281);
  assert.equal(page.end, 283);
});

test("paginate clamps a page above the last page", () => {
  const page = paginate(items, 99, 20);
  assert.equal(page.page, 15);
  assert.equal(page.start, 281);
});

test("paginate clamps page zero and negative pages to one", () => {
  assert.equal(paginate(items, 0, 20).page, 1);
  assert.equal(paginate(items, -4, 20).page, 1);
});

test("paginate handles an empty list", () => {
  const page = paginate([], 3, 20);
  assert.deepEqual(page.items, []);
  assert.equal(page.page, 1);
  assert.equal(page.totalPages, 1);
  assert.equal(page.start, 0);
  assert.equal(page.end, 0);
});

test("paginate treats a non-positive page size as one", () => {
  const page = paginate(items, 2, 0);
  assert.equal(page.pageSize, 1);
  assert.deepEqual(page.items, [2]);
  assert.equal(page.totalPages, 283);
});

test("paginate handles a page size larger than the list", () => {
  const page = paginate(items, 1, 500);
  assert.equal(page.items.length, 283);
  assert.equal(page.totalPages, 1);
  assert.equal(page.end, 283);
});

/* ── 三态 ── */

test("listState reports loading before everything else", () => {
  assert.equal(
    listState({ isLoading: true, hasError: true, itemCount: 0 }),
    "loading",
  );
});

test("listState reports error before empty", () => {
  assert.equal(
    listState({ isLoading: false, hasError: true, itemCount: 0 }),
    "error",
  );
});

test("listState reports empty only without error", () => {
  assert.equal(
    listState({ isLoading: false, hasError: false, itemCount: 0 }),
    "empty",
  );
  assert.equal(
    listState({ isLoading: false, hasError: false, itemCount: 3 }),
    "ready",
  );
});

/* ── 可执行性 ── */

test("executability prioritises permanent block", () => {
  const view = executabilityOf(
    tool({ permanently_blocked: true, executable_now: true }),
  );
  assert.equal(view.state, "permanently_blocked");
  assert.equal(view.tone, "muted");
});

test("executability reports a disabled catalog entry", () => {
  const view = executabilityOf(
    withAvailability({ executable: false }, {
      availability: "disabled",
      catalog_status: "disabled",
      last_test_status: null,
      last_test_at: null,
      last_records_count: null,
      missing_configuration: [],
    }),
  );
  assert.equal(view.state, "disabled");
});

test("executability reports missing configuration", () => {
  const view = executabilityOf(
    withAvailability({ executable_now: false }, {
      availability: "config-gated",
      catalog_status: "verified",
      last_test_status: null,
      last_test_at: null,
      last_records_count: null,
      missing_configuration: ["BRAVE_API_KEY"],
    }),
  );
  assert.equal(view.state, "config_gated");
  assert.equal(view.detail.includes("BRAVE_API_KEY"), true);
});

test("executability reports a catalog entry without a run path", () => {
  const view = executabilityOf(tool({ executable: false }));
  assert.equal(view.state, "unsupported");
});

test("executability reports the current environment gate", () => {
  const view = executabilityOf(tool({ executable_now: false }));
  assert.equal(view.state, "env_gated");
  assert.equal(view.tone, "info");
});

test("executability reports a runnable tool", () => {
  const view = executabilityOf(tool());
  assert.equal(view.state, "available");
  assert.equal(view.tone, "success");
});

/* ── 成本提示 ── */

test("costHint keeps an upstream estimate distinct from a price", () => {
  const view = costHintOf(
    tool({ cost: { summary: "每次约 $0.01", source: "upstream_estimate" } }),
  );
  assert.equal(view.text, "每次约 $0.01");
  assert.equal(view.sourceLabel, "上游估算");
  assert.equal(view.isEstimate, true);
  assert.equal(view.note.includes("不是平台售价"), true);
});

test("costHint reports a platform price", () => {
  const view = costHintOf(
    tool({ cost: { summary: "$5 / 1000 次", source: "platform_price" } }),
  );
  assert.equal(view.sourceLabel, "平台售价");
  assert.equal(view.isEstimate, false);
});

test("costHint reports an unknown cost without inventing a value", () => {
  const view = costHintOf(tool({ cost: { summary: null, source: "unknown" } }));
  assert.equal(view.text, "未登记成本");
  assert.equal(view.sourceLabel, "来源未知");
  assert.equal(view.isEstimate, false);
});

test("costHint treats a blank summary as missing", () => {
  const view = costHintOf(tool({ cost: { summary: "   ", source: "unknown" } }));
  assert.equal(view.text, "未登记成本");
});
