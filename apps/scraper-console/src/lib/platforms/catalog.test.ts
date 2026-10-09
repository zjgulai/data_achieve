import assert from "node:assert/strict";
import test from "node:test";

import {
  categoryKeyForPlatforms,
  datasetCategory,
  getPlatformLabel,
  getPlatformMeta,
  matchCategory,
} from "./catalog.ts";

test("maps a real platform to its category tab", () => {
  assert.equal(categoryKeyForPlatforms(["tiktok"]), "social_global");
  assert.equal(categoryKeyForPlatforms(["amazon"]), "ecommerce");
  assert.equal(categoryKeyForPlatforms(["zhihu"]), "social_cn");
});

test("falls back to the backend category when platforms are unknown", () => {
  assert.equal(categoryKeyForPlatforms([], "ecommerce"), "ecommerce");
  assert.equal(categoryKeyForPlatforms([], "open_web"), "open_web");
  assert.equal(categoryKeyForPlatforms([], "osint_tools"), "osint_tools");
});

test("defaults to 'all' when nothing matches", () => {
  assert.equal(categoryKeyForPlatforms([]), "all");
  assert.equal(categoryKeyForPlatforms(["not_a_real_platform"]), "all");
  assert.equal(categoryKeyForPlatforms([], "unknown_category"), "all");
});

test("datasetCategory prefers real platforms over dataset_type", () => {
  // ssh: a public_content dataset whose records actually came from 小红书
  assert.equal(datasetCategory(["xiaohongshu"], "public_content_update"), "social_global");
  // no lineage -> coarse mapping from dataset_type
  assert.equal(datasetCategory([], "ecommerce_product"), "ecommerce");
  assert.equal(datasetCategory([], "github_tool_radar"), "osint_tools");
});

test("matchCategory treats an empty filter list as match-all", () => {
  assert.equal(matchCategory("anything", []), true);
  assert.equal(matchCategory("tiktok", ["tiktok"]), true);
  assert.equal(matchCategory("tiktok", ["weibo"]), false);
});

test("platform labels fall back to a de-underscored key", () => {
  assert.equal(getPlatformLabel("tiktok"), "TikTok");
  assert.equal(getPlatformLabel("some_new_platform"), "some new platform");
});

test("platform meta falls back to a letter badge for unknown platforms", () => {
  const meta = getPlatformMeta("zzz");
  assert.equal(meta.letter, "ZZ");
  assert.equal(getPlatformMeta("tiktok").letter, "T");
});
