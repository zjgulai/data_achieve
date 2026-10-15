import assert from "node:assert/strict";
import test from "node:test";
import { canStartCollection } from "./collection-policy.ts";

test("policy restriction overrides a historically verified endpoint", () => {
  assert.equal(canStartCollection({ status: "verified", policy_block_reason: "未批准外访" }), false);
});
test("an available endpoint without a policy restriction can run", () => {
  assert.equal(canStartCollection({ status: "verified", policy_block_reason: null }), true);
});
test("disabled endpoints cannot run even without a policy reason", () => {
  assert.equal(canStartCollection({ status: "disabled" }), false);
});
