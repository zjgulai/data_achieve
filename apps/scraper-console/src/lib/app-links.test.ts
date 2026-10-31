import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { INSIGHT_URL, resolveAppUrl } from "./app-links.ts";

test("the insight URL defaults to the same-origin mount", () => {
  assert.equal(resolveAppUrl(undefined, "/insight"), "/insight");
  assert.equal(resolveAppUrl("", "/insight"), "/insight");
  assert.equal(resolveAppUrl("   ", "/insight"), "/insight");
});

test("an absolute override is kept as is", () => {
  assert.equal(
    resolveAppUrl("http://localhost:3000", "/insight"),
    "http://localhost:3000",
  );
  assert.equal(
    resolveAppUrl("https://scrapy.example.com/insight/", "/insight"),
    "https://scrapy.example.com/insight",
  );
});

test("a bare path gets a leading slash and no trailing slash", () => {
  assert.equal(resolveAppUrl("insight/", "/insight"), "/insight");
  assert.equal(resolveAppUrl("/insight/", "/insight"), "/insight");
});

test("the exported URL is a usable href", () => {
  assert.match(INSIGHT_URL, /^(?:\/|https?:\/\/)/);
});

test("the console top bar uses the shared constant", () => {
  const source = readFileSync(
    fileURLToPath(
      new URL("../components/layout/top-bar.tsx", import.meta.url),
    ),
    "utf8",
  );
  assert.match(source, /from "@\/lib\/app-links"/);
  assert.match(source, /href=\{INSIGHT_URL\}/);
  assert.equal(source.includes('"/insight"'), false);
});
