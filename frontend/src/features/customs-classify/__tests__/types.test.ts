import { describe, it, expect } from "vitest";

import { confidenceTier, formatProbability } from "../model/types";

describe("formatProbability", () => {
  it("renders as percentage with one decimal", () => {
    expect(formatProbability(0.85)).toBe("85.0%");
    expect(formatProbability(0.854)).toBe("85.4%");
  });

  it("handles edge values", () => {
    expect(formatProbability(0)).toBe("0.0%");
    expect(formatProbability(1)).toBe("100.0%");
  });
});

describe("confidenceTier", () => {
  it("classifies probability into high/medium/low", () => {
    expect(confidenceTier(0.95)).toBe("high");
    expect(confidenceTier(0.7)).toBe("high"); // boundary inclusive
    expect(confidenceTier(0.69)).toBe("medium");
    expect(confidenceTier(0.4)).toBe("medium"); // boundary inclusive
    expect(confidenceTier(0.39)).toBe("low");
    expect(confidenceTier(0)).toBe("low");
  });
});
