import assert from "node:assert/strict";
import test from "node:test";

import {
  parseRunReceipt,
  previewValue,
  readDurationMs,
  readUsageCost,
  recordPreviewEntries,
} from "./quick-collect-receipt.ts";

/* ── usage 金额 ─────────────────────────────────────────────────────────── */

test("reads cost from the preferred usage key", () => {
  assert.equal(readUsageCost({ total_cost_usd: 0.0123 }), 0.0123);
});

test("falls back to secondary cost keys", () => {
  assert.equal(readUsageCost({ cost_usd: 1.5 }), 1.5);
  assert.equal(readUsageCost({ cost: 2 }), 2);
});

test("prefers total_cost_usd over the other keys", () => {
  assert.equal(
    readUsageCost({ total_cost_usd: 0.5, cost_usd: 9, cost: 9 }),
    0.5,
  );
});

test("returns null when usage has no numeric cost", () => {
  assert.equal(readUsageCost({}), null);
  assert.equal(readUsageCost({ total_cost_usd: "0.5" }), null);
  assert.equal(readUsageCost({ total_cost_usd: Number.NaN }), null);
  assert.equal(readUsageCost(undefined), null);
  assert.equal(readUsageCost(null), null);
});

test("keeps zero as a real cost, not missing", () => {
  // 免费端点的 0 与"价格未知"必须区分开。
  assert.equal(readUsageCost({ total_cost_usd: 0 }), 0);
});

/* ── timing 耗时 ────────────────────────────────────────────────────────── */

test("reads duration_ms", () => {
  assert.equal(readDurationMs({ duration_ms: 421 }), 421);
});

test("returns null for missing or non-numeric duration", () => {
  assert.equal(readDurationMs({}), null);
  assert.equal(readDurationMs({ duration_ms: "421" }), null);
  assert.equal(readDurationMs(undefined), null);
});

/* ── 单值预览 ───────────────────────────────────────────────────────────── */

test("previews scalars as themselves", () => {
  assert.equal(previewValue("abc"), "abc");
  assert.equal(previewValue(42), "42");
  assert.equal(previewValue(true), "true");
  assert.equal(previewValue(0), "0");
});

test("collapses whitespace and truncates long strings", () => {
  assert.equal(previewValue("a\n\nb   c"), "a b c");
  const long = "x".repeat(80);
  assert.equal(previewValue(long), `${"x".repeat(40)}…`);
});

test("renders null and undefined as a dash", () => {
  assert.equal(previewValue(null), "—");
  assert.equal(previewValue(undefined), "—");
});

test("summarises nested structures instead of dumping them", () => {
  assert.equal(previewValue([1, 2, 3]), "[3]");
  assert.equal(previewValue({ a: 1, b: 2 }), "{…}");
});

/* ── 记录预览 ───────────────────────────────────────────────────────────── */

test("takes only scalar fields and stops at the limit", () => {
  const entries = recordPreviewEntries(
    { title: "hello", count: 3, nested: { a: 1 }, list: [1], extra: "tail" },
    3,
  );
  assert.deepEqual(entries, [
    ["title", "hello"],
    ["count", "3"],
    ["extra", "tail"],
  ]);
});

test("returns an empty list for a record with only nested values", () => {
  assert.deepEqual(recordPreviewEntries({ a: { b: 1 }, c: [1] }), []);
});

/* ── 整体解析 ───────────────────────────────────────────────────────────── */

test("parses a full receipt", () => {
  const receipt = parseRunReceipt({
    records: [{ title: "one" }, { title: "two" }],
    output: { query: "ai", total: 2 },
    usage: { total_cost_usd: 0.02 },
    timing: { duration_ms: 900 },
    records_count: 2,
  });

  assert.equal(receipt.durationMs, 900);
  assert.equal(receipt.costUsd, 0.02);
  assert.equal(receipt.recordsCount, 2);
  assert.equal(receipt.sample.length, 2);
});

test("uses records_count rather than the sample length", () => {
  // 后端只回前 20 条样本，但总数可能是 200。标题必须报真实总数。
  const receipt = parseRunReceipt({
    records: [{ a: 1 }],
    records_count: 200,
  });
  assert.equal(receipt.recordsCount, 200);
  assert.equal(receipt.sample.length, 1);
});

test("caps the sample at the requested limit", () => {
  const records = Array.from({ length: 10 }, (_, i) => ({ i }));
  assert.equal(parseRunReceipt({ records }, 3).sample.length, 3);
  assert.equal(parseRunReceipt({ records }, 5).sample.length, 5);
});

test("tolerates a failed run with no records or usage", () => {
  const receipt = parseRunReceipt({
    records: [],
    output: {},
    usage: {},
    timing: {},
    records_count: 0,
  });
  assert.equal(receipt.recordsCount, 0);
  assert.equal(receipt.sample.length, 0);
  assert.equal(receipt.durationMs, null);
  assert.equal(receipt.costUsd, null);
});

test("tolerates fields that are entirely absent", () => {
  // 旧版后端或异常响应可能一个字段都不给，页面不能因此崩。
  const receipt = parseRunReceipt({});
  assert.equal(receipt.recordsCount, 0);
  assert.equal(receipt.sample.length, 0);
  assert.equal(receipt.durationMs, null);
  assert.equal(receipt.costUsd, null);
});

test("skips non-object entries in the records array", () => {
  const receipt = parseRunReceipt({
    records: [{ ok: 1 }, "junk", null, 42],
    records_count: 4,
  });
  assert.equal(receipt.sample.length, 1);
  assert.equal(receipt.recordsCount, 4);
});

test("ignores a non-array records field", () => {
  const receipt = parseRunReceipt({ records: "not-an-array", records_count: 7 });
  assert.equal(receipt.sample.length, 0);
  assert.equal(receipt.recordsCount, 7);
});

test("falls back to sample length when records_count is unusable", () => {
  assert.equal(
    parseRunReceipt({ records: [{ a: 1 }, { a: 2 }] }).recordsCount,
    2,
  );
  assert.equal(
    parseRunReceipt({ records: [{ a: 1 }], records_count: "5" }).recordsCount,
    1,
  );
});
