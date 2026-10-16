import assert from "node:assert/strict";
import test from "node:test";
import {
  KEPT_ROUTES,
  NEW_ROUTES,
  ROOT_ROUTE,
  ROUTE_REDIRECTS,
  buildRedirects,
  parametersOf,
} from "./routes.ts";

test("the redirect table has the seven frozen entries", () => {
  assert.equal(ROUTE_REDIRECTS.length, 7);
});

test("the old capability directory redirects to tools", () => {
  const r = ROUTE_REDIRECTS.find(x => x.source === "/platforms");
  assert.ok(r);
  assert.equal(r.destination, "/tools");
  assert.equal(r.permanent, true);
});

test("the platform package directory redirects to tools", () => {
  const r = ROUTE_REDIRECTS.find(x => x.source === "/skills");
  assert.ok(r);
  assert.equal(r.destination, "/tools");
});

test("the platform detail repoints to a tool detail", () => {
  const r = ROUTE_REDIRECTS.find(x => x.source === "/skills/:platformId");
  assert.ok(r);
  // 段名必须与 source 一致。Next.js 拒绝改名的重定向。
  assert.equal(r.destination, "/tools/:platformId");
  assert.deepEqual(parametersOf(r.destination), parametersOf(r.source));
});

test("the collector docs redirect to docs", () => {
  assert.equal(
    ROUTE_REDIRECTS.find(x => x.source === "/collector-docs")?.destination,
    "/docs"
  );
});

test("the collect result keeps its path parameter under runs", () => {
  const r = ROUTE_REDIRECTS.find(x => x.source === "/collect/:runId");
  assert.ok(r);
  assert.equal(r.destination, "/runs/:runId");
  // 段名由 snake_case 改为 camelCase。
  assert.deepEqual(parametersOf(r.source), ["runId"]);
});

test("datasets redirect to assets", () => {
  assert.equal(
    ROUTE_REDIRECTS.find(x => x.source === "/datasets")?.destination,
    "/assets"
  );
});

test("raw records redirect under assets", () => {
  assert.equal(
    ROUTE_REDIRECTS.find(x => x.source === "/raw-records")?.destination,
    "/assets/records"
  );
});

test("every redirect preserves its path parameters", () => {
  // 参数个数要一致。/skills/:platformId 目标改名为 :toolId，值仍保留。
  for (const r of ROUTE_REDIRECTS) {
    const from = parametersOf(r.source);
    const to = parametersOf(r.destination);
    assert.equal(
      to.length,
      from.length,
      `${r.source} 有 ${from.length} 个参数，目标 ${r.destination} 有 ${to.length} 个`
    );
  }
});

test("no source path collides with a destination path", () => {
  const sources = new Set(ROUTE_REDIRECTS.map(r => r.source));
  for (const r of ROUTE_REDIRECTS) {
    assert.equal(
      sources.has(r.destination),
      false,
      `${r.destination} 既是目标又是来源，会形成重定向链`
    );
  }
});

test("kept routes are not redirected", () => {
  const sources = new Set(ROUTE_REDIRECTS.map(r => r.source));
  for (const kept of KEPT_ROUTES) {
    assert.equal(sources.has(kept), false, `${kept} 保持路径，不应出现在重定向表`);
  }
});

test("the three groups cover the frozen table exactly once", () => {
  // 冻结表共 15 条现有路由。
  // 根路由自成一类：路径不变，用途由重定向改为公开首页。
  assert.equal(
    ROUTE_REDIRECTS.length + KEPT_ROUTES.length + (ROOT_ROUTE ? 1 : 0),
    15
  );
  assert.equal(NEW_ROUTES.length, 4);
});

test("the root route is not itself a redirect", () => {
  // 新 IA 里 / 是真实页面，不是重定向。
  assert.equal(
    ROUTE_REDIRECTS.some(r => r.source === ROOT_ROUTE),
    false
  );
});

test("buildRedirects drops the note field", () => {
  const out = buildRedirects();
  assert.equal(out.length, ROUTE_REDIRECTS.length);
  for (const r of out) {
    assert.deepEqual(Object.keys(r).sort(), ["destination", "permanent", "source"]);
  }
});

test("every redirect is permanent", () => {
  for (const r of ROUTE_REDIRECTS) assert.equal(r.permanent, true);
});

test("each redirect states its purpose", () => {
  for (const r of ROUTE_REDIRECTS) assert.ok(r.note.length > 0, `${r.source} 缺说明`);
});
