import assert from "node:assert/strict";
import test from "node:test";

import { isSuccessfulRunStatus } from "./run-status.ts";

test("treats the API success status as a successful run", () => {
  assert.equal(isSuccessfulRunStatus("success"), true);
});

test("keeps completed compatibility and rejects failed runs", () => {
  assert.equal(isSuccessfulRunStatus("completed"), true);
  assert.equal(isSuccessfulRunStatus("failed"), false);
});
