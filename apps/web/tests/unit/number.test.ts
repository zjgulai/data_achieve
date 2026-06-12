import { describe, expect, it } from "vitest";

import { formatPercent } from "@/lib/formatters/number";

describe("formatPercent", () => {
  it("rounds a numeric value and appends percent sign", () => {
    expect(formatPercent(92.6)).toBe("93%");
  });
});
