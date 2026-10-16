import assert from "node:assert/strict";
import test from "node:test";
import { hrefWithParams, mergeParams } from "./url-state.ts";

test("mergeParams sets a new key", () => {
  const out = mergeParams(new URLSearchParams(), { cat: "ecommerce" });
  assert.equal(out, "cat=ecommerce");
});

test("mergeParams keeps existing keys", () => {
  const out = mergeParams(new URLSearchParams("cat=ecommerce"), { q: "shoe" });
  assert.equal(out, "cat=ecommerce&q=shoe");
});

test("mergeParams deletes a key when the value is null", () => {
  const out = mergeParams(new URLSearchParams("cat=ecommerce&q=shoe"), { cat: null });
  assert.equal(out, "q=shoe");
});

test("mergeParams deletes a key when the value is an empty string", () => {
  const out = mergeParams(new URLSearchParams("q=shoe"), { q: "" });
  assert.equal(out, "");
});

test("mergeParams does not modify the input", () => {
  const current = new URLSearchParams("cat=ecommerce");
  mergeParams(current, { cat: null, q: "x" });
  assert.equal(current.toString(), "cat=ecommerce");
});

test("mergeParams encodes Chinese and spaces", () => {
  const out = mergeParams(new URLSearchParams(), { q: "母婴 推荐" });
  const back = new URLSearchParams(out);
  assert.equal(back.get("q"), "母婴 推荐");
});

test("mergeParams round-trips a label containing a slash", () => {
  const out = mergeParams(new URLSearchParams(), {
    ep: "public_feed",
    label: "RSS/Atom 订阅源",
  });
  const back = new URLSearchParams(out);
  assert.equal(back.get("ep"), "public_feed");
  assert.equal(back.get("label"), "RSS/Atom 订阅源");
});

test("mergeParams produces a stable order", () => {
  const a = mergeParams(new URLSearchParams(), { q: "x", cat: "ads" });
  const b = mergeParams(new URLSearchParams(), { cat: "ads", q: "x" });
  assert.equal(a, b);
});

test("hrefWithParams omits the question mark when the query is empty", () => {
  assert.equal(hrefWithParams("/platforms", ""), "/platforms");
});

test("hrefWithParams appends the query string", () => {
  assert.equal(hrefWithParams("/platforms", "cat=ads"), "/platforms?cat=ads");
});
