import { describe, it, expect } from "vitest";
import { normalizeHsCode } from "../hs-code";

describe("normalizeHsCode", () => {
  it("strips spaces from a copy-pasted code", () => {
    expect(normalizeHsCode("4002 31 0000")).toBe("4002310000");
  });

  it("strips dots from a copy-pasted code", () => {
    expect(normalizeHsCode("4002.31.0000")).toBe("4002310000");
  });

  it("strips dashes from a copy-pasted code", () => {
    expect(normalizeHsCode("4002-31-0000")).toBe("4002310000");
  });

  it("strips mixed separators and surrounding whitespace", () => {
    expect(normalizeHsCode("  4002.31 0000 ")).toBe("4002310000");
  });

  it("leaves an already-clean 10-digit code untouched", () => {
    expect(normalizeHsCode("4002310000")).toBe("4002310000");
  });

  it("returns empty string for empty input", () => {
    expect(normalizeHsCode("")).toBe("");
  });

  it("returns empty string for null", () => {
    expect(normalizeHsCode(null)).toBe("");
  });

  it("returns empty string for undefined", () => {
    expect(normalizeHsCode(undefined)).toBe("");
  });

  it("returns empty string when input has no digits", () => {
    expect(normalizeHsCode("abc.-")).toBe("");
  });
});
