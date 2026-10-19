import assert from "node:assert/strict";
import test from "node:test";

import {
  isCompletedRunStatus,
  isSuccessfulRunStatus,
  runStatusMeta,
} from "./run-status.ts";

test("maps success to a green successful status", () => {
  assert.equal(isSuccessfulRunStatus("success"), true);
  assert.equal(isCompletedRunStatus("success"), true);

  const meta = runStatusMeta("success");
  assert.equal(meta.label, "成功");
  assert.equal(meta.tone, "success");
  assert.equal(meta.icon, "check");
});

test("maps completed to a green successful status", () => {
  assert.equal(isSuccessfulRunStatus("completed"), true);
  assert.equal(isCompletedRunStatus("completed"), true);

  const meta = runStatusMeta("completed");
  assert.equal(meta.label, "已完成");
  assert.equal(meta.tone, "success");
  assert.equal(meta.icon, "check");
});

test("maps partial_success to a warning completed status", () => {
  assert.equal(isSuccessfulRunStatus("partial_success"), false);
  assert.equal(isCompletedRunStatus("partial_success"), true);

  const meta = runStatusMeta("partial_success");
  assert.equal(meta.label, "部分成功");
  assert.equal(meta.tone, "warning");
  assert.equal(meta.icon, "alert");
  assert.notEqual(meta.description, "");
});

test("maps empty to a warning completed status", () => {
  assert.equal(isSuccessfulRunStatus("empty"), false);
  assert.equal(isCompletedRunStatus("empty"), true);

  const meta = runStatusMeta("empty");
  assert.equal(meta.label, "完成但无数据");
  assert.equal(meta.tone, "warning");
  assert.equal(meta.icon, "inbox");
  assert.match(meta.description, /没有取到数据/);
});

test("maps failed to a danger failed status", () => {
  assert.equal(isSuccessfulRunStatus("failed"), false);
  assert.equal(isCompletedRunStatus("failed"), false);

  const meta = runStatusMeta("failed");
  assert.equal(meta.label, "失败");
  assert.equal(meta.tone, "danger");
  assert.equal(meta.icon, "alert");
});

test("maps running to an info in-progress status", () => {
  assert.equal(isCompletedRunStatus("running"), false);

  const meta = runStatusMeta("running");
  assert.equal(meta.label, "运行中");
  assert.equal(meta.tone, "info");
  assert.equal(meta.icon, "loader");
});

test("maps pending to a neutral waiting status", () => {
  assert.equal(isCompletedRunStatus("pending"), false);

  const meta = runStatusMeta("pending");
  assert.equal(meta.label, "等待中");
  assert.equal(meta.tone, "neutral");
  assert.equal(meta.icon, "clock");
});

test("keeps unknown status text and uses neutral styling", () => {
  const meta = runStatusMeta("mystery_status");
  assert.equal(meta.label, "mystery_status");
  assert.equal(meta.tone, "neutral");
  assert.equal(meta.icon, "clock");
});
