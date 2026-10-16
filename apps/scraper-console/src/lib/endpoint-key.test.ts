import assert from "node:assert/strict";
import test from "node:test";
import { endpointRowKey } from "./endpoint-key.ts";

test("row key joins endpoint type and label", () => {
  assert.equal(
    endpointRowKey({ endpoint_type: "public_feed", label: "Forbes Innovation RSS" }),
    "public_feed:Forbes Innovation RSS"
  );
});

test("two rows of the same type get different keys", () => {
  const a = endpointRowKey({ endpoint_type: "public_feed", label: "A" });
  const b = endpointRowKey({ endpoint_type: "public_feed", label: "B" });
  assert.notEqual(a, b);
});

test("different types with the same label do not collide", () => {
  const a = endpointRowKey({ endpoint_type: "public_feed", label: "简介" });
  const b = endpointRowKey({ endpoint_type: "generic_web", label: "简介" });
  assert.notEqual(a, b);
});
